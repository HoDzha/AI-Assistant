from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from app.api.routes import get_task_service, get_task_store
from app.main import app
from app.models.api import (
    AnalysisOverview,
    AnalyzeResponse,
    DayPlanEntry,
    DayPlanTask,
    PrioritizedTask,
    ProjectSummary,
)
from app.services.openai_client import OpenAITransientError
from app.storage.sqlite import SqliteTaskStore


class StubTaskService:
    def __init__(self, response: AnalyzeResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def analyze(self, request):  # noqa: ANN001
        if self._error is not None:
            raise self._error
        assert request.tasks
        assert self._response is not None
        return self._response


@pytest.fixture
def client_with_sqlite_store(tmp_path):
    store = SqliteTaskStore(f"sqlite:///{(tmp_path / 'api-tasks.db').as_posix()}")
    app.dependency_overrides[get_task_store] = lambda: store
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def test_health_check() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "timestamp" in body


def test_analyze_endpoint_returns_service_response(sample_request) -> None:
    stub_response = AnalyzeResponse(
        generated_at=datetime.now(timezone.utc),
        overview=AnalysisOverview(
            summary="Work the urgent issue first.",
            total_tasks=2,
            total_estimated_hours=5.0,
            working_hours_per_day=6,
            overloaded_today=False,
        ),
        prioritized_tasks=[
            PrioritizedTask(
                id="task-001",
                title="Fix urgent production bug",
                project="Client Beta CRM",
                client="Beta",
                github_url="https://github.com/example/client-beta-crm",
                status="in_progress",
                type="development",
                deadline="2026-03-25",
                days_until_deadline=0,
                estimated_hours=2,
                importance="critical",
                ai_priority="critical",
                priority_reason="Production bug affects leads.",
                recommended_order=1,
                recommended_day="Today",
                recommended_time_block="09:00-11:00",
                should_do_today=True,
                risk="Revenue impact if delayed.",
            )
        ],
        day_plan=[
            DayPlanEntry(
                day_label="Today",
                date="2026-03-25",
                total_planned_hours=2.0,
                tasks=[
                    DayPlanTask(
                        task_id="task-001",
                        title="Fix urgent production bug",
                        project="Client Beta CRM",
                        status="in_progress",
                        planned_hours=2.0,
                        focus="Fix the critical bug.",
                        github_url="https://github.com/example/client-beta-crm",
                    )
                ],
            )
        ],
        recommendations=["Protect two hours of uninterrupted work."],
        project_summaries=[
            ProjectSummary(
                project_name="Client Beta CRM",
                github_url="https://github.com/example/client-beta-crm",
                total_tasks=1,
                todo_count=0,
                in_progress_count=1,
                blocked_count=0,
                done_count=0,
                overall_status="in_progress",
            )
        ],
    )
    app.dependency_overrides[get_task_service] = lambda: StubTaskService(response=stub_response)
    client = TestClient(app)

    response = client.post("/api/analyze", json=sample_request.model_dump(mode="json"))

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["overview"]["summary"] == "Work the urgent issue first."
    assert body["prioritized_tasks"][0]["id"] == "task-001"


def test_analyze_endpoint_maps_transient_errors(sample_request) -> None:
    app.dependency_overrides[get_task_service] = lambda: StubTaskService(
        error=OpenAITransientError("Service temporarily unavailable.")
    )
    client = TestClient(app)

    response = client.post("/api/analyze", json=sample_request.model_dump(mode="json"))

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"] == "Service temporarily unavailable."


def test_task_endpoints_persist_and_return_tasks(sample_request, client_with_sqlite_store) -> None:
    task_payload = sample_request.tasks[0].model_dump(mode="json")

    create_response = client_with_sqlite_store.post("/api/tasks", json=task_payload)

    assert create_response.status_code == 201
    assert create_response.json()["id"] == "task-001"

    list_response = client_with_sqlite_store.get("/api/tasks")

    assert list_response.status_code == 200
    assert list_response.json()["tasks"][0]["id"] == "task-001"


def test_task_replace_endpoint_overwrites_collection(sample_request, client_with_sqlite_store) -> None:
    payload = {"tasks": sample_request.model_dump(mode="json")["tasks"]}

    response = client_with_sqlite_store.put("/api/tasks", json=payload)

    assert response.status_code == 200
    assert [task["id"] for task in response.json()["tasks"]] == ["task-001", "task-002"]


def test_task_delete_endpoint_removes_task(sample_request, client_with_sqlite_store) -> None:
    client_with_sqlite_store.put(
        "/api/tasks",
        json={"tasks": sample_request.model_dump(mode="json")["tasks"]},
    )

    delete_response = client_with_sqlite_store.delete("/api/tasks/task-001")

    assert delete_response.status_code == 204
    remaining = client_with_sqlite_store.get("/api/tasks")
    assert [task["id"] for task in remaining.json()["tasks"]] == ["task-002"]


def test_task_update_endpoint_updates_existing_task(sample_request, client_with_sqlite_store) -> None:
    original_task = sample_request.tasks[0].model_dump(mode="json")
    client_with_sqlite_store.post("/api/tasks", json=original_task)
    updated_task = {
        **original_task,
        "title": "Fix urgent production bug and notify client",
        "status": "done",
        "archived": True,
    }

    response = client_with_sqlite_store.put("/api/tasks/task-001", json=updated_task)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Fix urgent production bug and notify client"
    assert body["status"] == "done"
    assert body["archived"] is True
