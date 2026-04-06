from __future__ import annotations

import json
import time
from datetime import date
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.api import EnrichedTask, LlmTaskAnalysis, UserContext
from app.services.analysis_cache import InMemoryAnalysisCache
from app.services.openai_client import OpenAITaskAnalyzer
from app.services.task_service import TaskAnalysisService
from app.storage.factory import build_task_store


class FakeAnalyzer:
    def __init__(self, result: LlmTaskAnalysis) -> None:
        self._result = result
        self.calls = 0

    def analyze_tasks(
        self,
        user_context: UserContext,
        tasks: list[EnrichedTask],
    ) -> LlmTaskAnalysis:
        self.calls += 1
        assert user_context.current_date == date(2026, 3, 25)
        assert len(tasks) == 2
        return self._result


def test_task_service_builds_response(sample_request) -> None:
    analyzer = FakeAnalyzer(
        LlmTaskAnalysis.model_validate(
            {
                "summary": "Focus on the production issue first.",
                "prioritized_tasks": [
                    {
                        "id": "task-001",
                        "ai_priority": "critical",
                        "priority_reason": "Production bug affects leads.",
                        "recommended_order": 1,
                        "recommended_day": "Today",
                        "recommended_time_block": "09:00-11:00",
                        "should_do_today": True,
                        "risk": "Revenue impact if delayed.",
                    }
                ],
                "day_plan": [
                    {
                        "day_label": "Today",
                        "date": "2026-03-25",
                        "tasks": [
                            {
                                "task_id": "task-001",
                                "planned_hours": 2,
                                "focus": "Fix the critical bug.",
                            }
                        ],
                    }
                ],
                "recommendations": ["Finish the bugfix before content work."],
            }
        )
    )

    response = TaskAnalysisService(analyzer).analyze(sample_request)

    assert analyzer.calls == 1
    assert response.overview.total_tasks == 2
    assert response.overview.total_estimated_hours == 5.0
    assert response.prioritized_tasks[0].id == "task-001"
    assert response.prioritized_tasks[0].recommended_order == 1
    assert response.prioritized_tasks[1].id == "task-002"
    assert response.day_plan[0].tasks[0].task_id == "task-001"
    assert response.project_summaries[0].project_name == "Alpha Landing"
    assert response.recommendations == ["Finish the bugfix before content work."]


def test_openai_analyzer_uses_cache() -> None:
    settings = Settings(
        openai_api_key="test-key",
        openai_cache_ttl_seconds=60,
        openai_cache_max_entries=10,
    )
    cache = InMemoryAnalysisCache(ttl_seconds=60, max_entries=10)
    analyzer = OpenAITaskAnalyzer(settings, cache=cache)

    context = UserContext(
        current_date=date(2026, 3, 25),
        working_hours_per_day=6,
        user_name="Alex",
        work_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
    )
    task = EnrichedTask.model_validate(
        {
            "id": "task-001",
            "title": "Fix urgent production bug",
            "description": "Repair broken email signup flow.",
            "project": "Client Beta CRM",
            "client": "Beta",
            "github_url": "https://github.com/example/client-beta-crm",
            "type": "development",
            "deadline": "2026-03-25",
            "estimated_hours": 2,
            "importance": "critical",
            "status": "in_progress",
            "tags": ["backend", "urgent"],
            "dependencies": [],
            "notes": "Affects new leads.",
            "days_until_deadline": 0,
            "urgency_label": "today",
            "workload_bucket": "small",
        }
    )

    payload = {
        "summary": "Cached summary",
        "prioritized_tasks": [],
        "day_plan": [],
        "recommendations": [],
    }
    cache_key = analyzer._cache_key(context, [task])
    cache.set(cache_key, json.dumps(payload))

    def fail_if_called() -> SimpleNamespace:
        raise AssertionError("OpenAI client should not be called when cache is warm")

    analyzer._get_client = fail_if_called  # type: ignore[method-assign]

    result = analyzer.analyze_tasks(context, [task])

    assert result.summary == "Cached summary"


def test_cache_returns_none_for_missing_key() -> None:
    cache = InMemoryAnalysisCache(ttl_seconds=60, max_entries=2)

    assert cache.get("missing") is None


def test_cache_expires_entries() -> None:
    cache = InMemoryAnalysisCache(ttl_seconds=0, max_entries=2)
    cache.set("soon-expired", "value")
    time.sleep(0.01)

    assert cache.get("soon-expired") is None


def test_cache_evicts_oldest_entries() -> None:
    cache = InMemoryAnalysisCache(ttl_seconds=60, max_entries=2)
    cache.set("first", "one")
    cache.set("second", "two")
    cache.set("third", "three")

    assert cache.get("first") is None
    assert cache.get("second") == "two"
    assert cache.get("third") == "three"


def test_identical_inputs_generate_same_cache_key() -> None:
    settings = Settings(openai_api_key="test-key")
    analyzer = OpenAITaskAnalyzer(settings)
    context = UserContext(
        current_date=date(2026, 3, 25),
        working_hours_per_day=6,
        user_name="Alex",
        work_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
    )
    task_payload = {
        "id": "task-001",
        "title": "Fix urgent production bug",
        "description": "Repair broken email signup flow.",
        "project": "Client Beta CRM",
        "client": "Beta",
        "github_url": "https://github.com/example/client-beta-crm",
        "type": "development",
        "deadline": "2026-03-25",
        "estimated_hours": 2,
        "importance": "critical",
        "status": "in_progress",
        "tags": ["backend", "urgent"],
        "dependencies": [],
        "notes": "Affects new leads.",
        "days_until_deadline": 0,
        "urgency_label": "today",
        "workload_bucket": "small",
    }
    first_task = EnrichedTask.model_validate(task_payload)
    second_task = EnrichedTask.model_validate(task_payload)

    assert analyzer._cache_key(context, [first_task]) == analyzer._cache_key(context, [second_task])


def test_settings_reject_invalid_openai_base_url() -> None:
    with pytest.raises(ValueError):
        Settings(openai_base_url="api.openai.com/v1")


def test_settings_reject_invalid_database_url() -> None:
    with pytest.raises(ValueError):
        Settings(database_url="postgresql://localhost/freelance-flow")


def test_task_store_factory_rejects_unsupported_database_engine() -> None:
    with pytest.raises(ValueError):
        build_task_store("postgresql:///freelance-flow")
