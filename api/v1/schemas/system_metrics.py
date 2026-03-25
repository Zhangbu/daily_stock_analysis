# -*- coding: utf-8 -*-
"""System metrics API schemas."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class SlowOperationItem(BaseModel):
    """One slow operation sample."""

    operation: str
    provider: str
    status: str
    duration_ms: int


class MetricTrendItem(BaseModel):
    """One recent trend bucket for an operation."""

    bucket_ts: int
    count: int
    success: int
    error: int
    cache_hits: int
    cache_misses: int
    total_duration_ms: int
    max_duration_ms: int
    avg_duration_ms: int


class SystemMetricsResponse(BaseModel):
    """Runtime metrics snapshot for API/Web observability."""

    observability: Dict[str, Dict[str, int]]
    observability_by_provider: Dict[str, Dict[str, int]]
    observability_trends: Dict[str, List[MetricTrendItem]]
    recent_slowest: List[SlowOperationItem]
    cache: Dict[str, Dict[str, Any]]


class CacheClearResponse(BaseModel):
    """Response payload for cache clear actions."""

    success: bool
    namespace: str
    cleared_namespaces: List[str]
    cache: Dict[str, Dict[str, Any]]
