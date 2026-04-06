from __future__ import annotations

import threading
import time
from collections import OrderedDict


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
