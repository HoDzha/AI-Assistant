from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings
from app.services.analysis_cache import (
    AnalysisCacheProto,
    InMemoryAnalysisCache,
    PersistentAnalysisCache,
)
from app.storage.base import TaskStore
from app.storage.sqlite import SqliteTaskStore


@lru_cache(maxsize=4)
def build_task_store(database_url: str) -> TaskStore:
    """Create a task store implementation for the configured database URL."""

    if database_url.startswith("sqlite:///"):
        return SqliteTaskStore(database_url)
    raise ValueError("Unsupported database engine configured in DATABASE_URL.")


def get_configured_task_store(settings: Settings) -> TaskStore:
    """Return the shared task store for the current settings."""

    return build_task_store(settings.database_url)


def get_analysis_cache(
    cache_backend: str,
    cache_file: str,
    ttl_seconds: int,
    max_entries: int,
) -> AnalysisCacheProto:
    """Create an analysis cache matching the configured backend."""

    if cache_backend == "persistent":
        return PersistentAnalysisCache(
            database_path=cache_file,
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
        )
    return InMemoryAnalysisCache(
        ttl_seconds=ttl_seconds,
        max_entries=max_entries,
    )
