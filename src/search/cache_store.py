# -*- coding: utf-8 -*-
"""Shared cache store and metrics for search-related operations."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, Optional


class SearchCacheStore:
    """Lightweight in-memory cache with namespace-level metrics."""

    def __init__(self) -> None:
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._stats = defaultdict(
            lambda: {
                "hits": 0,
                "misses": 0,
                "writes": 0,
                "evictions": 0,
                "entries": 0,
            }
        )

    def get(self, namespace: str, key: str, ttl_seconds: int) -> Optional[Any]:
        """Return cached value if not expired."""
        entry = self._cache.get(f"{namespace}:{key}")
        if entry is None:
            self._stats[namespace]["misses"] += 1
            return None
        timestamp, value = entry
        if ttl_seconds > 0 and time.time() - timestamp > ttl_seconds:
            del self._cache[f"{namespace}:{key}"]
            self._stats[namespace]["misses"] += 1
            self._stats[namespace]["evictions"] += 1
            self._refresh_entries(namespace)
            return None
        self._stats[namespace]["hits"] += 1
        return value

    def put(self, namespace: str, key: str, value: Any, max_entries: int = 500) -> None:
        """Store a cached value and enforce a simple per-namespace size cap."""
        full_key = f"{namespace}:{key}"
        self._cache[full_key] = (time.time(), value)
        self._stats[namespace]["writes"] += 1

        namespace_keys = [k for k in self._cache if k.startswith(f"{namespace}:")]
        if len(namespace_keys) > max_entries:
            oldest = sorted(namespace_keys, key=lambda item: self._cache[item][0])[: len(namespace_keys) - max_entries]
            for evict_key in oldest:
                del self._cache[evict_key]
                self._stats[namespace]["evictions"] += 1
        self._refresh_entries(namespace)

    def stats(self) -> Dict[str, Dict[str, int]]:
        """Return cache statistics by namespace."""
        snapshot: Dict[str, Dict[str, int]] = {}
        for namespace, values in self._stats.items():
            item = dict(values)
            total = item["hits"] + item["misses"]
            item["hit_rate_pct"] = int(item["hits"] / total * 100) if total else 0
            snapshot[namespace] = item
        return snapshot

    def clear(self) -> None:
        """Clear all cache entries and metrics."""
        self._cache.clear()
        self._stats.clear()

    def clear_namespace(self, namespace: str) -> None:
        """Clear cache entries and metrics for one namespace."""
        keys = [key for key in self._cache if key.startswith(f"{namespace}:")]
        for key in keys:
            del self._cache[key]
        self._stats.pop(namespace, None)

    def _refresh_entries(self, namespace: str) -> None:
        self._stats[namespace]["entries"] = sum(1 for key in self._cache if key.startswith(f"{namespace}:"))


search_cache_store = SearchCacheStore()
