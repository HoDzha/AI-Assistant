from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from app.models.api import TaskInput
from app.storage.base import DuplicateTaskError, TaskNotFoundError, TaskStore


class SqliteTaskStore(TaskStore):
    """SQLite-backed task storage implementation."""

    def __init__(self, database_url: str) -> None:
        self._database_path = self._resolve_database_path(database_url)
        self._initialization_lock = threading.Lock()
        self._initialized = False
        self._ensure_initialized()

    def list_tasks(self) -> list[TaskInput]:
        self._ensure_initialized()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    project,
                    client,
                    github_url,
                    type,
                    deadline,
                    estimated_hours,
                    importance,
                    status,
                    archived,
                    tags_json,
                    dependencies_json,
                    notes
                FROM tasks
                ORDER BY id
                """
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def create_task(self, task: TaskInput) -> TaskInput:
        self._ensure_initialized()
        payload = self._serialize_task(task)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO tasks (
                        id,
                        title,
                        description,
                        project,
                        client,
                        github_url,
                        type,
                        deadline,
                        estimated_hours,
                        importance,
                        status,
                        archived,
                        tags_json,
                        dependencies_json,
                        notes
                    ) VALUES (
                        :id,
                        :title,
                        :description,
                        :project,
                        :client,
                        :github_url,
                        :type,
                        :deadline,
                        :estimated_hours,
                        :importance,
                        :status,
                        :archived,
                        :tags_json,
                        :dependencies_json,
                        :notes
                    )
                    """,
                    payload,
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTaskError(f"Task with id '{task.id}' already exists.") from exc
        return task

    def update_task(self, task_id: str, task: TaskInput) -> TaskInput:
        self._ensure_initialized()
        payload = self._serialize_task(task)
        payload["lookup_id"] = task_id
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE tasks
                    SET
                        id = :id,
                        title = :title,
                        description = :description,
                        project = :project,
                        client = :client,
                        github_url = :github_url,
                        type = :type,
                        deadline = :deadline,
                        estimated_hours = :estimated_hours,
                        importance = :importance,
                        status = :status,
                        archived = :archived,
                        tags_json = :tags_json,
                        dependencies_json = :dependencies_json,
                        notes = :notes,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :lookup_id
                    """,
                    payload,
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTaskError(f"Task with id '{task.id}' already exists.") from exc

        if cursor.rowcount == 0:
            raise TaskNotFoundError(f"Task with id '{task_id}' was not found.")
        return task

    def replace_tasks(self, tasks: list[TaskInput]) -> list[TaskInput]:
        self._ensure_initialized()
        self._validate_unique_ids(tasks)
        serialized_tasks = [self._serialize_task(task) for task in tasks]
        with self._connect() as connection:
            connection.execute("DELETE FROM tasks")
            if serialized_tasks:
                connection.executemany(
                    """
                    INSERT INTO tasks (
                        id,
                        title,
                        description,
                        project,
                        client,
                        github_url,
                        type,
                        deadline,
                        estimated_hours,
                        importance,
                        status,
                        archived,
                        tags_json,
                        dependencies_json,
                        notes
                    ) VALUES (
                        :id,
                        :title,
                        :description,
                        :project,
                        :client,
                        :github_url,
                        :type,
                        :deadline,
                        :estimated_hours,
                        :importance,
                        :status,
                        :archived,
                        :tags_json,
                        :dependencies_json,
                        :notes
                    )
                    """,
                    serialized_tasks,
                )
        return tasks

    def delete_task(self, task_id: str) -> None:
        self._ensure_initialized()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise TaskNotFoundError(f"Task with id '{task_id}' was not found.")

    @staticmethod
    def _validate_unique_ids(tasks: list[TaskInput]) -> None:
        task_ids = [task.id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise DuplicateTaskError("Task collection contains duplicate ids.")

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        with self._initialization_lock:
            if self._initialized:
                return

            if self._database_path != Path(":memory:"):
                self._database_path.parent.mkdir(parents=True, exist_ok=True)

            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT,
                        project TEXT,
                        client TEXT,
                        github_url TEXT,
                        type TEXT NOT NULL,
                        deadline TEXT NOT NULL,
                        estimated_hours REAL,
                        importance TEXT NOT NULL,
                        status TEXT NOT NULL,
                        archived INTEGER NOT NULL DEFAULT 0,
                        tags_json TEXT NOT NULL,
                        dependencies_json TEXT NOT NULL,
                        notes TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                try:
                    connection.execute(
                        """
                        ALTER TABLE tasks
                        ADD COLUMN archived INTEGER NOT NULL DEFAULT 0
                        """
                    )
                except sqlite3.OperationalError:
                    pass
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _resolve_database_path(database_url: str) -> Path:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Unsupported database URL. Expected sqlite:///...")

        raw_path = database_url.removeprefix(prefix)
        if raw_path == ":memory:":
            return Path(":memory:")

        return Path(raw_path)

    @staticmethod
    def _serialize_task(task: TaskInput) -> dict[str, object]:
        payload = task.model_dump(mode="json")
        return {
            "id": payload["id"],
            "title": payload["title"],
            "description": payload["description"],
            "project": payload["project"],
            "client": payload["client"],
            "github_url": payload["github_url"],
            "type": payload["type"],
            "deadline": payload["deadline"],
            "estimated_hours": payload["estimated_hours"],
            "importance": payload["importance"],
            "status": payload["status"],
            "archived": int(payload["archived"]),
            "tags_json": json.dumps(payload["tags"], ensure_ascii=False),
            "dependencies_json": json.dumps(payload["dependencies"], ensure_ascii=False),
            "notes": payload["notes"],
        }

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskInput:
        return TaskInput.model_validate(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "project": row["project"],
                "client": row["client"],
                "github_url": row["github_url"],
                "type": row["type"],
                "deadline": row["deadline"],
                "estimated_hours": row["estimated_hours"],
                "importance": row["importance"],
                "status": row["status"],
                "archived": bool(row["archived"]),
                "tags": json.loads(row["tags_json"]),
                "dependencies": json.loads(row["dependencies_json"]),
                "notes": row["notes"],
            }
        )
