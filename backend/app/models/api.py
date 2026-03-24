from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TaskImportance = Literal["low", "medium", "high", "critical"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done"]
ProjectStatus = Literal["planned", "in_progress", "attention_needed", "done"]
TaskPriority = Literal["low", "medium", "high", "critical"]


class UserContext(BaseModel):
    """Context about the freelancer's current work mode."""

    model_config = ConfigDict(extra="forbid")

    current_date: date
    working_hours_per_day: Annotated[int, Field(ge=1, le=16)] = 8
    user_name: str | None = None
    work_days: list[str] = Field(
        default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri"]
    )


class TaskInput(BaseModel):
    """Task payload accepted by the backend."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyStr
    title: NonEmptyStr
    description: str | None = None
    project: str | None = None
    client: str | None = None
    github_url: AnyHttpUrl | None = None
    type: NonEmptyStr
    deadline: date
    estimated_hours: Annotated[float | None, Field(gt=0, le=24)] = None
    importance: TaskImportance = "medium"
    status: TaskStatus = "todo"
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    notes: str | None = None


class AnalyzeRequest(BaseModel):
    """Request body for task analysis."""

    model_config = ConfigDict(extra="forbid")

    user_context: UserContext
    tasks: Annotated[list[TaskInput], Field(min_length=1)]


class EnrichedTask(TaskInput):
    """Task with computed scheduling metadata."""

    days_until_deadline: int
    urgency_label: str
    workload_bucket: str


class LlmPrioritizedTask(BaseModel):
    """Task-level analysis returned by the model."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyStr
    ai_priority: TaskPriority
    priority_reason: NonEmptyStr
    recommended_order: Annotated[int, Field(ge=1)]
    recommended_day: NonEmptyStr
    recommended_time_block: NonEmptyStr
    should_do_today: bool
    risk: str | None = None


class LlmDayPlanTask(BaseModel):
    """Task placement in a generated plan."""

    model_config = ConfigDict(extra="forbid")

    task_id: NonEmptyStr
    planned_hours: Annotated[float, Field(gt=0, le=24)]
    focus: NonEmptyStr


class LlmDayPlanEntry(BaseModel):
    """Day plan entry returned by the model."""

    model_config = ConfigDict(extra="forbid")

    day_label: NonEmptyStr
    date: str | None = None
    tasks: list[LlmDayPlanTask] = Field(default_factory=list)


class LlmTaskAnalysis(BaseModel):
    """Structured output expected from OpenAI."""

    model_config = ConfigDict(extra="forbid")

    summary: NonEmptyStr
    prioritized_tasks: list[LlmPrioritizedTask] = Field(default_factory=list)
    day_plan: list[LlmDayPlanEntry] = Field(default_factory=list)
    recommendations: list[NonEmptyStr] = Field(default_factory=list)


class AnalysisOverview(BaseModel):
    """High-level overview of the analysis result."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    total_tasks: int
    total_estimated_hours: float
    working_hours_per_day: int
    overloaded_today: bool


class PrioritizedTask(BaseModel):
    """Task data returned to the frontend after analysis."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    project: str | None = None
    client: str | None = None
    github_url: AnyHttpUrl | None = None
    status: TaskStatus
    type: str
    deadline: date
    days_until_deadline: int
    estimated_hours: float | None = None
    importance: TaskImportance
    ai_priority: TaskPriority
    priority_reason: str
    recommended_order: int
    recommended_day: str
    recommended_time_block: str
    should_do_today: bool
    risk: str | None = None


class DayPlanTask(BaseModel):
    """Frontend-ready representation of a planned task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    title: str
    project: str | None = None
    status: TaskStatus
    planned_hours: float
    focus: str
    github_url: AnyHttpUrl | None = None


class DayPlanEntry(BaseModel):
    """Frontend-ready representation of a day plan."""

    model_config = ConfigDict(extra="forbid")

    day_label: str
    date: str | None = None
    total_planned_hours: float
    tasks: list[DayPlanTask] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Aggregated project status summary."""

    model_config = ConfigDict(extra="forbid")

    project_name: str
    github_url: AnyHttpUrl | None = None
    total_tasks: int
    todo_count: int
    in_progress_count: int
    blocked_count: int
    done_count: int
    overall_status: ProjectStatus


class AnalyzeResponse(BaseModel):
    """Response returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    overview: AnalysisOverview
    prioritized_tasks: list[PrioritizedTask]
    day_plan: list[DayPlanEntry]
    recommendations: list[str]
    project_summaries: list[ProjectSummary]


class HealthResponse(BaseModel):
    """Basic health response."""

    model_config = ConfigDict(extra="forbid")

    status: str
    timestamp: datetime
