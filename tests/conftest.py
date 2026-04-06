from __future__ import annotations

from datetime import date

import pytest

from app.models.api import AnalyzeRequest, UserContext


@pytest.fixture
def sample_request() -> AnalyzeRequest:
    return AnalyzeRequest.model_validate(
        {
            "user_context": {
                "current_date": date(2026, 3, 25),
                "working_hours_per_day": 6,
                "user_name": "Alex",
                "work_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            },
            "tasks": [
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
                },
                {
                    "id": "task-002",
                    "title": "Prepare launch copy",
                    "description": "Draft hero section and benefits.",
                    "project": "Alpha Landing",
                    "client": "Alpha",
                    "github_url": "https://github.com/example/alpha-landing",
                    "type": "content",
                    "deadline": "2026-03-27",
                    "estimated_hours": 3,
                    "importance": "high",
                    "status": "todo",
                    "tags": ["copywriting"],
                    "dependencies": [],
                    "notes": None,
                },
            ],
        }
    )
