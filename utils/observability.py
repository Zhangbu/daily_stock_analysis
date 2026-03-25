# -*- coding: utf-8 -*-
"""Lightweight observability helpers for latency and operation metrics."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from utils.log_utils import build_log_context


class InMemoryMetricsStore:
    """Store basic counters and latency summaries for local observability."""

    def __init__(self) -> None:
        self._trend_bucket_seconds = 60
        self._trend_retention_buckets = 10
        self._metrics = defaultdict(
            lambda: {
                "count": 0,
                "success": 0,
                "error": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "total_duration_ms": 0,
                "max_duration_ms": 0,
            }
        )
        self._provider_metrics = defaultdict(
            lambda: {
                "count": 0,
                "success": 0,
                "error": 0,
                "total_duration_ms": 0,
                "max_duration_ms": 0,
            }
        )
        self._recent_slowest: List[Dict[str, object]] = []
        self._trend_metrics = defaultdict(
            lambda: {
                "count": 0,
                "success": 0,
                "error": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "total_duration_ms": 0,
                "max_duration_ms": 0,
            }
        )

    def record(
        self,
        *,
        operation: str,
        status: str,
        duration_ms: int,
        cache_hit: Optional[bool] = None,
        provider: Optional[str] = None,
    ) -> None:
        """Record one operation event."""
        metric = self._metrics[operation]
        metric["count"] += 1
        metric["total_duration_ms"] += duration_ms
        metric["max_duration_ms"] = max(metric["max_duration_ms"], duration_ms)
        if status == "ok":
            metric["success"] += 1
        else:
            metric["error"] += 1
        if cache_hit is True:
            metric["cache_hits"] += 1
        elif cache_hit is False:
            metric["cache_misses"] += 1
        if provider:
            provider_key = f"{operation}:{provider}"
            provider_metric = self._provider_metrics[provider_key]
            provider_metric["count"] += 1
            provider_metric["total_duration_ms"] += duration_ms
            provider_metric["max_duration_ms"] = max(provider_metric["max_duration_ms"], duration_ms)
            if status == "ok":
                provider_metric["success"] += 1
            else:
                provider_metric["error"] += 1
        self._record_slow_event(
            operation=operation,
            provider=provider,
            status=status,
            duration_ms=duration_ms,
        )
        self._record_trend_event(
            operation=operation,
            status=status,
            duration_ms=duration_ms,
            cache_hit=cache_hit,
        )

    def snapshot(self) -> Dict[str, Dict[str, int]]:
        """Return a serializable metrics snapshot."""
        snapshot: Dict[str, Dict[str, int]] = {}
        for operation, metric in self._metrics.items():
            item = dict(metric)
            item["avg_duration_ms"] = (
                int(metric["total_duration_ms"] / metric["count"]) if metric["count"] else 0
            )
            snapshot[operation] = item
        return snapshot

    def provider_snapshot(self) -> Dict[str, Dict[str, int]]:
        """Return per-operation provider latency and status snapshot."""
        snapshot: Dict[str, Dict[str, int]] = {}
        for key, metric in self._provider_metrics.items():
            item = dict(metric)
            item["avg_duration_ms"] = (
                int(metric["total_duration_ms"] / metric["count"]) if metric["count"] else 0
            )
            snapshot[key] = item
        return snapshot

    def recent_slowest(self, limit: int = 10) -> List[Dict[str, object]]:
        """Return the most recent slowest operation events."""
        return list(self._recent_slowest[:limit])

    def trend_snapshot(self) -> Dict[str, List[Dict[str, int]]]:
        """Return recent minute-level trend buckets by operation."""
        snapshot: Dict[str, List[Dict[str, int]]] = {}
        trend_points: Dict[str, List[Dict[str, int]]] = defaultdict(list)
        for bucket_key, metric in sorted(self._trend_metrics.items()):
            operation, bucket_ts = bucket_key
            item = dict(metric)
            item["bucket_ts"] = bucket_ts
            item["avg_duration_ms"] = (
                int(metric["total_duration_ms"] / metric["count"]) if metric["count"] else 0
            )
            trend_points[operation].append(item)

        for operation, points in trend_points.items():
            snapshot[operation] = points[-self._trend_retention_buckets :]
        return snapshot

    def clear(self) -> None:
        """Reset all in-memory metrics."""
        self._metrics.clear()
        self._provider_metrics.clear()
        self._recent_slowest.clear()
        self._trend_metrics.clear()

    def _record_slow_event(
        self,
        *,
        operation: str,
        provider: Optional[str],
        status: str,
        duration_ms: int,
    ) -> None:
        self._recent_slowest.append(
            {
                "operation": operation,
                "provider": provider or "",
                "status": status,
                "duration_ms": duration_ms,
            }
        )
        self._recent_slowest.sort(key=lambda item: int(item["duration_ms"]), reverse=True)
        del self._recent_slowest[20:]

    def _record_trend_event(
        self,
        *,
        operation: str,
        status: str,
        duration_ms: int,
        cache_hit: Optional[bool],
    ) -> None:
        bucket_ts = int(time.time() // self._trend_bucket_seconds * self._trend_bucket_seconds)
        bucket_key = (operation, bucket_ts)
        trend_metric = self._trend_metrics[bucket_key]
        trend_metric["count"] += 1
        trend_metric["total_duration_ms"] += duration_ms
        trend_metric["max_duration_ms"] = max(trend_metric["max_duration_ms"], duration_ms)
        if status == "ok":
            trend_metric["success"] += 1
        else:
            trend_metric["error"] += 1
        if cache_hit is True:
            trend_metric["cache_hits"] += 1
        elif cache_hit is False:
            trend_metric["cache_misses"] += 1

        min_bucket_ts = bucket_ts - self._trend_bucket_seconds * self._trend_retention_buckets
        expired_keys = [key for key in self._trend_metrics if key[1] < min_bucket_ts]
        for key in expired_keys:
            del self._trend_metrics[key]


metrics_store = InMemoryMetricsStore()


def emit_operation_log(
    logger: logging.Logger,
    *,
    operation: str,
    status: str,
    duration_ms: int,
    level: int = logging.INFO,
    message: str = "",
    **fields: object,
) -> None:
    """Emit a structured operation log."""
    context = build_log_context(**fields)
    parts = [part for part in [context, f"op={operation}", f"status={status}", f"duration_ms={duration_ms}", message] if part]
    logger.log(level, " ".join(parts))


class OperationTimer:
    """Context manager that records latency and status for one operation."""

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        *,
        success_level: int = logging.INFO,
        failure_level: int = logging.ERROR,
        metric_store: InMemoryMetricsStore = metrics_store,
        **fields: object,
    ) -> None:
        self.logger = logger
        self.operation = operation
        self.success_level = success_level
        self.failure_level = failure_level
        self.metric_store = metric_store
        self.fields = dict(fields)
        self.message = ""
        self._start = 0.0
        self._status_override: Optional[str] = None

    def __enter__(self) -> "OperationTimer":
        self._start = time.perf_counter()
        return self

    def update(self, **fields: object) -> None:
        """Add or override contextual fields before the operation completes."""
        self.fields.update(fields)

    def set_message(self, message: str) -> None:
        """Attach a short message to the eventual log event."""
        self.message = message

    def mark_failed(self, message: str = "") -> None:
        """Mark the operation as failed even if the exception is handled upstream."""
        self._status_override = "error"
        if message:
            self.message = message

    def __exit__(self, exc_type, exc, _tb) -> bool:
        duration_ms = int((time.perf_counter() - self._start) * 1000)
        status = self._status_override or ("error" if exc_type else "ok")
        level = self.failure_level if exc_type else self.success_level
        if status == "error":
            level = self.failure_level
        if exc is not None and not self.message:
            self.message = str(exc)
        cache_hit = self.fields.get("cache_hit")
        provider = self.fields.get("provider")
        self.metric_store.record(
            operation=self.operation,
            status=status,
            duration_ms=duration_ms,
            cache_hit=cache_hit if isinstance(cache_hit, bool) else None,
            provider=str(provider) if provider else None,
        )
        emit_operation_log(
            self.logger,
            operation=self.operation,
            status=status,
            duration_ms=duration_ms,
            level=level,
            message=self.message,
            **self.fields,
        )
        return False
