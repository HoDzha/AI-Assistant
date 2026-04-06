from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings
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
