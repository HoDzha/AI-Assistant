from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from app.models.api import (
    AnalysisOverview,
    AnalyzeRequest,
    AnalyzeResponse,
    DayPlanEntry,
    DayPlanTask,
    EnrichedTask,
    LlmDayPlanEntry,
    LlmPrioritizedTask,
    PrioritizedTask,
    ProjectStatus,
    ProjectSummary,
    TaskImportance,
    TaskInput,
    TaskPriority,
    TaskStatus,
)
from app.services.openai_client import OpenAITaskAnalyzer


_IMPORTANCE_WEIGHTS: dict[TaskImportance, int] = {
    "low": 10,
    "medium": 20,
    "high": 35,
    "critical": 50,
}
_STATUS_WEIGHTS: dict[TaskStatus, int] = {
    "todo": 0,
    "in_progress": 10,
    "blocked": -5,
    "done": -100,
}
_WEEKDAY_INDEX: dict[str, int] = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}


class TaskAnalysisService:
    """Coordinate task enrichment, OpenAI analysis and response shaping."""

    def __init__(self, analyzer: OpenAITaskAnalyzer) -> None:
        self._analyzer = analyzer

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Analyze tasks and return a frontend-ready response."""

        enriched_tasks = [
            self._enrich_task(task, request.user_context.current_date)
            for task in request.tasks
        ]
        analysis = self._analyzer.analyze_tasks(request.user_context, enriched_tasks)
        prioritized_tasks = self._build_prioritized_tasks(
            enriched_tasks,
            analysis.prioritized_tasks,
        )
        day_plan = self._build_day_plan(
            request,
            enriched_tasks,
            prioritized_tasks,
            analysis.day_plan,
        )
        total_estimated_hours = round(
            sum(task.estimated_hours or 0.0 for task in request.tasks),
            2,
        )
        project_summaries = self._build_project_summaries(request.tasks)
        overloaded_today = (
            total_estimated_hours > float(request.user_context.working_hours_per_day)
        )

        return AnalyzeResponse(
            generated_at=datetime.now(timezone.utc),
            overview=AnalysisOverview(
                summary=analysis.summary,
                total_tasks=len(request.tasks),
                total_estimated_hours=total_estimated_hours,
                working_hours_per_day=request.user_context.working_hours_per_day,
                overloaded_today=overloaded_today,
            ),
            prioritized_tasks=prioritized_tasks,
            day_plan=day_plan,
            recommendations=analysis.recommendations,
            project_summaries=project_summaries,
        )

    @staticmethod
    def _enrich_task(task: TaskInput, current_date: date) -> EnrichedTask:
        days_until_deadline = (task.deadline - current_date).days
        urgency_label = (
            "overdue"
            if days_until_deadline < 0
            else "today"
            if days_until_deadline == 0
            else "urgent"
            if days_until_deadline <= 2
            else "soon"
            if days_until_deadline <= 7
            else "planned"
        )
        estimated_hours = task.estimated_hours or 0.0
        workload_bucket = (
            "small"
            if estimated_hours <= 2
            else "medium"
            if estimated_hours <= 5
            else "large"
        )
        return EnrichedTask(
            **task.model_dump(),
            days_until_deadline=days_until_deadline,
            urgency_label=urgency_label,
            workload_bucket=workload_bucket,
        )

    def _build_prioritized_tasks(
        self,
        enriched_tasks: list[EnrichedTask],
        llm_priorities: list[LlmPrioritizedTask],
    ) -> list[PrioritizedTask]:
        llm_by_id = {item.id: item for item in llm_priorities}
        fallback_order = self._fallback_sorted_tasks(enriched_tasks)
        valid_task_ids = {task.id for task in enriched_tasks}

        ordered_ids: list[str] = []
        for item in sorted(
            llm_priorities,
            key=lambda value: (value.recommended_order, value.id),
        ):
            if item.id in valid_task_ids and item.id not in ordered_ids:
                ordered_ids.append(item.id)

        for task in fallback_order:
            if task.id not in ordered_ids:
                ordered_ids.append(task.id)

        tasks_by_id = {task.id: task for task in enriched_tasks}
        response: list[PrioritizedTask] = []
        for index, task_id in enumerate(ordered_ids, start=1):
            task = tasks_by_id[task_id]
            llm_item = llm_by_id.get(task_id)
            fallback_priority, fallback_reason = self._fallback_priority(task)
            response.append(
                PrioritizedTask(
                    id=task.id,
                    title=task.title,
                    project=task.project,
                    client=task.client,
                    github_url=task.github_url,
                    status=task.status,
                    type=task.type,
                    deadline=task.deadline,
                    days_until_deadline=task.days_until_deadline,
                    estimated_hours=task.estimated_hours,
                    importance=task.importance,
                    ai_priority=llm_item.ai_priority if llm_item else fallback_priority,
                    priority_reason=llm_item.priority_reason if llm_item else fallback_reason,
                    recommended_order=index,
                    recommended_day=llm_item.recommended_day if llm_item else "Сегодня",
                    recommended_time_block=(
                        llm_item.recommended_time_block
                        if llm_item
                        else self._fallback_time_block(task)
                    ),
                    should_do_today=(
                        llm_item.should_do_today
                        if llm_item
                        else task.status == "in_progress" or task.days_until_deadline <= 1
                    ),
                    risk=llm_item.risk if llm_item else self._fallback_risk(task),
                )
            )
        return response

    def _build_day_plan(
        self,
        request: AnalyzeRequest,
        enriched_tasks: list[EnrichedTask],
        prioritized_tasks: list[PrioritizedTask],
        llm_day_plan: list[LlmDayPlanEntry],
    ) -> list[DayPlanEntry]:
        mapped_plan = self._map_llm_day_plan(enriched_tasks, llm_day_plan)
        if mapped_plan:
            return mapped_plan
        return self._build_fallback_day_plan(request, prioritized_tasks)

    @staticmethod
    def _map_llm_day_plan(
        enriched_tasks: list[EnrichedTask],
        llm_day_plan: list[LlmDayPlanEntry],
    ) -> list[DayPlanEntry]:
        tasks_by_id = {task.id: task for task in enriched_tasks}
        response: list[DayPlanEntry] = []
        for day in llm_day_plan:
            day_tasks: list[DayPlanTask] = []
            for item in day.tasks:
                task = tasks_by_id.get(item.task_id)
                if task is None:
                    continue
                day_tasks.append(
                    DayPlanTask(
                        task_id=task.id,
                        title=task.title,
                        project=task.project,
                        status=task.status,
                        planned_hours=item.planned_hours,
                        focus=item.focus,
                        github_url=task.github_url,
                    )
                )
            if not day_tasks:
                continue
            response.append(
                DayPlanEntry(
                    day_label=day.day_label,
                    date=day.date,
                    total_planned_hours=round(
                        sum(task.planned_hours for task in day_tasks),
                        2,
                    ),
                    tasks=day_tasks,
                )
            )
        return response

    def _build_fallback_day_plan(
        self,
        request: AnalyzeRequest,
        prioritized_tasks: list[PrioritizedTask],
    ) -> list[DayPlanEntry]:
        planned_days = self._next_work_dates(
            request.user_context.current_date,
            request.user_context.work_days,
            5,
        )
        if not planned_days:
            planned_days = [(request.user_context.current_date, "Сегодня")]

        remaining_capacity = {
            work_date.isoformat(): float(request.user_context.working_hours_per_day)
            for work_date, _ in planned_days
        }
        plan_map: dict[str, list[DayPlanTask]] = defaultdict(list)

        for task in prioritized_tasks:
            if task.status == "done":
                continue
            hours_left = task.estimated_hours or 1.0
            for work_date, _label in planned_days:
                date_key = work_date.isoformat()
                if remaining_capacity[date_key] <= 0:
                    continue
                allocation = min(hours_left, remaining_capacity[date_key])
                if allocation <= 0:
                    continue
                plan_map[date_key].append(
                    DayPlanTask(
                        task_id=task.id,
                        title=task.title,
                        project=task.project,
                        status=task.status,
                        planned_hours=round(allocation, 2),
                        focus=f"Сфокусироваться на задаче: {task.title}",
                        github_url=task.github_url,
                    )
                )
                remaining_capacity[date_key] -= allocation
                hours_left -= allocation
                if hours_left <= 0:
                    break

        response: list[DayPlanEntry] = []
        labels_by_date = {
            work_date.isoformat(): label for work_date, label in planned_days
        }
        for work_date, _label in planned_days:
            date_key = work_date.isoformat()
            tasks = plan_map.get(date_key, [])
            if not tasks:
                continue
            response.append(
                DayPlanEntry(
                    day_label=labels_by_date[date_key],
                    date=date_key,
                    total_planned_hours=round(
                        sum(task.planned_hours for task in tasks),
                        2,
                    ),
                    tasks=tasks,
                )
            )
        return response

    def _build_project_summaries(
        self,
        tasks: list[TaskInput],
    ) -> list[ProjectSummary]:
        grouped: dict[str, list[TaskInput]] = defaultdict(list)
        for task in tasks:
            grouped[task.project or "Без проекта"].append(task)

        response: list[ProjectSummary] = []
        for project_name, project_tasks in sorted(
            grouped.items(),
            key=lambda item: item[0].lower(),
        ):
            counts: defaultdict[str, int] = defaultdict(int)
            github_url = next(
                (task.github_url for task in project_tasks if task.github_url is not None),
                None,
            )
            for task in project_tasks:
                counts[task.status] += 1
            response.append(
                ProjectSummary(
                    project_name=project_name,
                    github_url=github_url,
                    total_tasks=len(project_tasks),
                    todo_count=counts["todo"],
                    in_progress_count=counts["in_progress"],
                    blocked_count=counts["blocked"],
                    done_count=counts["done"],
                    overall_status=self._project_status(
                        counts["todo"],
                        counts["in_progress"],
                        counts["blocked"],
                        counts["done"],
                    ),
                )
            )
        return response

    @staticmethod
    def _project_status(
        todo_count: int,
        in_progress_count: int,
        blocked_count: int,
        done_count: int,
    ) -> ProjectStatus:
        total_count = todo_count + in_progress_count + blocked_count + done_count
        if total_count > 0 and done_count == total_count:
            return "done"
        if blocked_count > 0:
            return "attention_needed"
        if in_progress_count > 0:
            return "in_progress"
        return "planned"

    def _fallback_sorted_tasks(self, tasks: list[EnrichedTask]) -> list[EnrichedTask]:
        return sorted(tasks, key=self._fallback_sort_key)

    def _fallback_sort_key(
        self,
        task: EnrichedTask,
    ) -> tuple[int, int, int, float, str]:
        score = self._priority_score(task)
        return (
            -score,
            task.days_until_deadline,
            0 if task.status != "done" else 1,
            task.estimated_hours or 999.0,
            task.id,
        )

    def _priority_score(self, task: EnrichedTask) -> int:
        deadline_weight = (
            100
            if task.days_until_deadline < 0
            else 90
            if task.days_until_deadline == 0
            else 80
            if task.days_until_deadline <= 1
            else 60
            if task.days_until_deadline <= 3
            else 40
            if task.days_until_deadline <= 7
            else 15
        )
        short_task_bonus = 5 if (task.estimated_hours or 0.0) <= 2 else 0
        dependency_bonus = 5 if task.dependencies else 0
        return (
            deadline_weight
            + _IMPORTANCE_WEIGHTS[task.importance]
            + _STATUS_WEIGHTS[task.status]
            + short_task_bonus
            + dependency_bonus
        )

    def _fallback_priority(self, task: EnrichedTask) -> tuple[TaskPriority, str]:
        score = self._priority_score(task)
        if score >= 120:
            priority: TaskPriority = "critical"
        elif score >= 90:
            priority = "high"
        elif score >= 50:
            priority = "medium"
        else:
            priority = "low"

        reasons: list[str] = []
        if task.days_until_deadline < 0:
            reasons.append("дедлайн уже просрочен")
        elif task.days_until_deadline <= 1:
            reasons.append("дедлайн очень близко")
        elif task.days_until_deadline <= 3:
            reasons.append("дедлайн наступает в ближайшие дни")

        if task.importance in {"high", "critical"}:
            reasons.append("задача отмечена как важная")
        if task.status == "in_progress":
            reasons.append("задача уже находится в работе")
        if task.status == "blocked":
            reasons.append("задача заблокирована и требует внимания")
        if task.dependencies:
            reasons.append("есть зависимости от других задач")

        reason_text = ", ".join(reasons) if reasons else "задача не выглядит срочной"
        return priority, reason_text.capitalize() + "."

    @staticmethod
    def _fallback_time_block(task: EnrichedTask) -> str:
        if task.status == "in_progress":
            return "Начать день с завершения текущего контекста"
        if task.days_until_deadline <= 1:
            return "Первый фокус-блок дня"
        if (task.estimated_hours or 0.0) <= 2:
            return "Короткий утренний слот"
        return "Основной дневной слот"

    @staticmethod
    def _fallback_risk(task: EnrichedTask) -> str | None:
        if task.status == "blocked":
            return "Без разблокировки задача может остановить дальнейший прогресс."
        if task.days_until_deadline < 0:
            return "Задача уже просрочена."
        if task.days_until_deadline <= 1:
            return "Высокий риск не успеть в срок."
        return None

    def _next_work_dates(
        self,
        start_date: date,
        work_days: Iterable[str],
        limit: int,
    ) -> list[tuple[date, str]]:
        allowed = {
            _WEEKDAY_INDEX.get(day, 0)
            for day in work_days
            if day in _WEEKDAY_INDEX
        }
        if not allowed:
            allowed = {0, 1, 2, 3, 4}

        results: list[tuple[date, str]] = []
        current_date = start_date
        while len(results) < limit:
            if current_date.weekday() in allowed:
                results.append(
                    (
                        current_date,
                        "Сегодня"
                        if current_date == start_date
                        else current_date.strftime("%d.%m"),
                    )
                )
            current_date = current_date + timedelta(days=1)
        return results
