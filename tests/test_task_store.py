from __future__ import annotations

import pytest

from app.storage.base import DuplicateTaskError, TaskNotFoundError
from app.storage.sqlite import SqliteTaskStore


def _database_url(tmp_path, filename: str = "tasks.db") -> str:
    return f"sqlite:///{(tmp_path / filename).as_posix()}"


def test_sqlite_task_store_persists_tasks_between_instances(sample_request, tmp_path) -> None:
    database_url = _database_url(tmp_path)
    first_store = SqliteTaskStore(database_url)

    first_store.create_task(sample_request.tasks[0])

    second_store = SqliteTaskStore(database_url)
    stored_tasks = second_store.list_tasks()

    assert len(stored_tasks) == 1
    assert stored_tasks[0].id == "task-001"
    assert stored_tasks[0].title == "Fix urgent production bug"


def test_sqlite_task_store_replaces_task_collection(sample_request, tmp_path) -> None:
    store = SqliteTaskStore(_database_url(tmp_path))

    stored_tasks = store.replace_tasks(sample_request.tasks)

    assert len(stored_tasks) == 2
    assert [task.id for task in store.list_tasks()] == ["task-001", "task-002"]


def test_sqlite_task_store_updates_existing_task(sample_request, tmp_path) -> None:
    store = SqliteTaskStore(_database_url(tmp_path))
    store.create_task(sample_request.tasks[0])
    updated_task = sample_request.tasks[0].model_copy(
        update={
            "title": "Fix urgent production bug and verify CRM sync",
            "status": "done",
            "archived": True,
        }
    )

    store.update_task("task-001", updated_task)

    stored_task = store.list_tasks()[0]
    assert stored_task.title == "Fix urgent production bug and verify CRM sync"
    assert stored_task.status == "done"
    assert stored_task.archived is True


def test_sqlite_task_store_rejects_duplicate_task_ids(sample_request, tmp_path) -> None:
    store = SqliteTaskStore(_database_url(tmp_path))

    with pytest.raises(DuplicateTaskError):
        store.replace_tasks([sample_request.tasks[0], sample_request.tasks[0]])


def test_sqlite_task_store_deletes_existing_task(sample_request, tmp_path) -> None:
    store = SqliteTaskStore(_database_url(tmp_path))
    store.replace_tasks(sample_request.tasks)

    store.delete_task("task-001")

    assert [task.id for task in store.list_tasks()] == ["task-002"]


def test_sqlite_task_store_raises_for_missing_task_delete(tmp_path) -> None:
    store = SqliteTaskStore(_database_url(tmp_path))

    with pytest.raises(TaskNotFoundError):
        store.delete_task("missing-task")


def test_sqlite_task_store_raises_for_missing_task_update(sample_request, tmp_path) -> None:
    store = SqliteTaskStore(_database_url(tmp_path))

    with pytest.raises(TaskNotFoundError):
        store.update_task("missing-task", sample_request.tasks[0])
