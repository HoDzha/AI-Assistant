from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.api import AnalyzeRequest, AnalyzeResponse, HealthResponse
from app.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIResponseError,
    OpenAITaskAnalyzer,
    OpenAITransientError,
)
from app.services.task_service import TaskAnalysisService


router = APIRouter()


def get_task_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TaskAnalysisService:
    """Create the task analysis service for a request."""

    analyzer = OpenAITaskAnalyzer(settings)
    return TaskAnalysisService(analyzer)


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return application health."""

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_tasks(
    request: AnalyzeRequest,
    service: Annotated[TaskAnalysisService, Depends(get_task_service)],
) -> AnalyzeResponse:
    """Analyze tasks and return a structured plan."""

    try:
        return service.analyze(request)
    except OpenAIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except OpenAITransientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenAIResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
