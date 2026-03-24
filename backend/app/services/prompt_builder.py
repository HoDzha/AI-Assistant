from __future__ import annotations

from app.models.api import EnrichedTask, UserContext


def build_system_prompt() -> str:
    """Return the system prompt for the OpenAI model."""

    return (
        "Ты ИИ-менеджер задач для фрилансеров. "
        "Твоя задача — анализировать список задач, определять приоритетность, "
        "выявлять риски и предлагать реалистичный порядок выполнения. "
        "Отвечай на русском языке. Учитывай дедлайны, текущие статусы, важность, "
        "оценку в часах, зависимости, GitHub-ссылки и рабочую нагрузку пользователя. "
        "Не придумывай задачи, которых нет во входных данных. "
        "Каждая входная задача должна появиться в ответе ровно один раз."
    )


def build_user_prompt(context: UserContext, tasks: list[EnrichedTask]) -> str:
    """Build the user prompt with structured task context."""

    person_name = context.user_name or "Фрилансер"
    task_blocks: list[str] = []

    for index, task in enumerate(tasks, start=1):
        dependencies = ", ".join(task.dependencies) if task.dependencies else "нет"
        tags = ", ".join(task.tags) if task.tags else "нет"
        task_blocks.append(
            "\n".join(
                [
                    f"Задача {index}:",
                    f"- id: {task.id}",
                    f"- title: {task.title}",
                    f"- project: {task.project or 'Без проекта'}",
                    f"- client: {task.client or 'Не указан'}",
                    f"- github_url: {task.github_url or 'Не указана'}",
                    f"- type: {task.type}",
                    f"- deadline: {task.deadline.isoformat()}",
                    f"- days_until_deadline: {task.days_until_deadline}",
                    f"- urgency_label: {task.urgency_label}",
                    f"- estimated_hours: {task.estimated_hours if task.estimated_hours is not None else 'Не указано'}",
                    f"- workload_bucket: {task.workload_bucket}",
                    f"- importance: {task.importance}",
                    f"- status: {task.status}",
                    f"- dependencies: {dependencies}",
                    f"- tags: {tags}",
                    f"- description: {task.description or 'Не указано'}",
                    f"- notes: {task.notes or 'Не указано'}",
                ]
            )
        )

    return (
        f"Пользователь: {person_name}\n"
        f"Текущая дата: {context.current_date.isoformat()}\n"
        f"Рабочих часов в день: {context.working_hours_per_day}\n"
        f"Рабочие дни: {', '.join(context.work_days)}\n\n"
        "Проанализируй задачи и верни:\n"
        "1. Краткое summary по рабочей ситуации.\n"
        "2. prioritized_tasks: для каждой задачи укажи ai_priority, "
        "priority_reason, recommended_order, recommended_day, "
        "recommended_time_block, should_do_today и risk.\n"
        "3. day_plan: сгруппируй задачи по дням и укажи planned_hours и focus.\n"
        "4. recommendations: 3-5 конкретных рекомендаций по организации работы.\n\n"
        "Список задач:\n"
        f"{chr(10).join(task_blocks)}"
    )
