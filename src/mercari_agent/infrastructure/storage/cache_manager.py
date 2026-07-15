"""Small asynchronous in-memory cache with TTL support."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class _CacheEntry:
    value: Any
    expires_at: Optional[float]


class CacheManager:
    """Provide the async cache interface consumed by ``LLMService``."""

    def __init__(self) -> None:
        self._entries: dict[str, _CacheEntry] = {}

    async def initialize(self) -> None:
        """Initialize the in-memory backend."""

    async def get(self, key: str) -> Any | None:
        """Return a value, dropping it first when its TTL has expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and entry.expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None
        return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Cache a value; a missing or non-positive TTL means no expiration."""
        expires_at = None
        if ttl is not None and ttl > 0:
            expires_at = time.monotonic() + ttl
        self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
        return True

    async def close(self) -> None:
        """Release all cached values."""
        self._entries.clear()
