from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.models.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    TaskCollectionPayload,
    TaskInput,
)
from app.services.analysis_cache import AnalysisCacheProto
from app.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIResponseError,
    OpenAITaskAnalyzer,
    OpenAITransientError,
)
from app.services.task_service import TaskAnalysisService
from app.storage import (
    DuplicateTaskError,
    TaskNotFoundError,
    TaskStore,
    get_analysis_cache,
    get_configured_task_store,
)

router = APIRouter()

AnalysisCache = AnalysisCacheProto


@lru_cache(maxsize=1)
def _get_shared_cache(
    cache_backend: str,
    cache_file: str,
    ttl_seconds: int,
    max_entries: int,
) -> AnalysisCache:
    """Return a singleton analysis cache instance."""

    return get_analysis_cache(cache_backend, cache_file, ttl_seconds, max_entries)


def get_analysis_cache_dep(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisCache:
    """Return the configured analysis cache for the current request."""

    return _get_shared_cache(
        settings.openai_cache_backend,
        settings.openai_cache_file,
        settings.openai_cache_ttl_seconds,
        settings.openai_cache_max_entries,
    )


def get_task_service(
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[AnalysisCache, Depends(get_analysis_cache_dep)],
) -> TaskAnalysisService:
    """Create the task analysis service with the configured cache."""

    analyzer = OpenAITaskAnalyzer(settings, cache=cache)
    return TaskAnalysisService(analyzer)


def get_task_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TaskStore:
    """Return the configured persistent task store."""

    return get_configured_task_store(settings)


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return application health."""

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/tasks", response_model=TaskCollectionPayload)
def list_tasks(
    store: Annotated[TaskStore, Depends(get_task_store)],
) -> TaskCollectionPayload:
    """Return tasks stored in persistent storage."""

    return TaskCollectionPayload(tasks=store.list_tasks())


@router.post("/tasks", response_model=TaskInput, status_code=status.HTTP_201_CREATED)
def create_task(
    task: TaskInput,
    store: Annotated[TaskStore, Depends(get_task_store)],
    cache: Annotated[AnalysisCache, Depends(get_analysis_cache_dep)],
) -> TaskInput:
    """Store a single task. Invalidates all cached analyses."""

    try:
        result = store.create_task(task)
    except DuplicateTaskError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    cache.clear()
    return result


@router.put("/tasks", response_model=TaskCollectionPayload)
def replace_tasks(
    payload: TaskCollectionPayload,
    store: Annotated[TaskStore, Depends(get_task_store)],
    cache: Annotated[AnalysisCache, Depends(get_analysis_cache_dep)],
) -> TaskCollectionPayload:
    """Replace the stored task collection. Invalidates all cached analyses."""

    try:
        result = TaskCollectionPayload(tasks=store.replace_tasks(payload.tasks))
    except DuplicateTaskError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    cache.clear()
    return result


@router.put("/tasks/{task_id}", response_model=TaskInput)
def update_task(
    task_id: str,
    task: TaskInput,
    store: Annotated[TaskStore, Depends(get_task_store)],
    cache: Annotated[AnalysisCache, Depends(get_analysis_cache_dep)],
) -> TaskInput:
    """Update a stored task. Invalidates all cached analyses."""

    try:
        result = store.update_task(task_id, task)
    except DuplicateTaskError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    cache.clear()
    return result


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    store: Annotated[TaskStore, Depends(get_task_store)],
    cache: Annotated[AnalysisCache, Depends(get_analysis_cache_dep)],
) -> None:
    """Delete a stored task. Invalidates all cached analyses."""

    try:
        store.delete_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    cache.clear()


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
