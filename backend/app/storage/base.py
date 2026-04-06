from __future__ import annotations

from typing import Protocol

from app.models.api import TaskInput


class DuplicateTaskError(RuntimeError):
    """Raised when a task with the same identifier already exists."""


class TaskNotFoundError(RuntimeError):
    """Raised when a task cannot be found in persistent storage."""


class TaskStore(Protocol):
    """Abstract task persistence contract."""

    def list_tasks(self) -> list[TaskInput]:
        """Return all stored tasks ordered for stable display."""

    def create_task(self, task: TaskInput) -> TaskInput:
        """Persist a new task."""

    def update_task(self, task_id: str, task: TaskInput) -> TaskInput:
        """Update an existing task."""

    def replace_tasks(self, tasks: list[TaskInput]) -> list[TaskInput]:
        """Replace the stored task collection with the provided list."""

    def delete_task(self, task_id: str) -> None:
        """Delete a task by identifier."""
