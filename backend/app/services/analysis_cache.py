from __future__ import annotations

import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Protocol


class AnalysisCacheProto(Protocol):
    """Protocol for analysis cache backends."""

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def clear(self) -> None: ...


class InMemoryAnalysisCache:
    """Simple TTL cache for serialized LLM analysis responses."""

    def __init__(self, ttl_seconds: int = 900, max_entries: int = 128) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get(self, key: str) -> str | None:
        """Return a cached value if it is present and not expired."""

        with self._lock:
            cached = self._items.get(key)
            if cached is None:
                return None

            expires_at, value = cached
            if expires_at < time.time():
                self._items.pop(key, None)
                return None

            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: str) -> None:
        """Store a serialized response and evict oldest items if needed."""

        with self._lock:
            self._items[key] = (time.time() + self._ttl_seconds, value)
            self._items.move_to_end(key)
            excess = len(self._items) - self._max_entries
            if excess > 0:
                for _ in range(excess):
                    self._items.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached entries."""

        with self._lock:
            self._items.clear()


class PersistentAnalysisCache:
    """SQLite-backed TTL cache for serialized LLM analysis responses.

    Survives server restarts. Uses a single SQLite database file for storage.
    """

    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS analysis_cache (
            cache_key TEXT PRIMARY KEY,
            response_json TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """

    def __init__(
        self,
        database_path: str,
        ttl_seconds: int = 3600,
        max_entries: int = 256,
    ) -> None:
        self._database_path = self._resolve_path(database_path)
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._ensure_initialized()

    def get(self, key: str) -> str | None:
        """Return a cached value if it is present and not expired."""

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT response_json, expires_at FROM analysis_cache WHERE cache_key = ?",
                    (key,),
                ).fetchone()

            if row is None:
                return None

            response_json: str = row["response_json"]
            expires_at: float = row["expires_at"]
            if expires_at < time.time():
                self._delete_key(key)
                return None

            return response_json

    def set(self, key: str, value: str) -> None:
        """Store a serialized response and evict oldest items if needed."""

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO analysis_cache (cache_key, response_json, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, value, time.time() + self._ttl_seconds),
                )

                self._evict_oldest(conn)

    def clear(self) -> None:
        """Remove all cached entries."""

        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM analysis_cache")

    def _evict_oldest(self, conn: sqlite3.Connection) -> None:
        """Delete the oldest entries when cache exceeds max_entries."""

        count = conn.execute("SELECT COUNT(*) FROM analysis_cache").fetchone()[0]
        excess = count - self._max_entries
        if excess > 0:
            conn.execute(
                """
                DELETE FROM analysis_cache
                WHERE cache_key IN (
                    SELECT cache_key FROM analysis_cache
                    ORDER BY expires_at ASC
                    LIMIT ?
                )
                """,
                (excess,),
            )

    def _delete_key(self, key: str) -> None:
        """Remove a single entry by cache key."""

        with self._connect() as conn:
            conn.execute("DELETE FROM analysis_cache WHERE cache_key = ?", (key,))

    def _ensure_initialized(self) -> None:
        """Create the cache table if it does not exist yet."""

        if self._database_path != Path(":memory:"):
            self._database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(self._CREATE_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        """Create a new database connection."""

        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _resolve_path(database_path: str) -> Path:
        """Resolve the database path from a URL or raw path."""

        if database_path.startswith("sqlite:///"):
            raw = database_path.removeprefix("sqlite:///")
        else:
            raw = database_path

        if raw == ":memory:":
            return Path(":memory:")

        return Path(raw)
