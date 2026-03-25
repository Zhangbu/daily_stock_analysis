# -*- coding: utf-8 -*-
"""System metrics endpoints."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.system_metrics import CacheClearResponse, SystemMetricsResponse
from data_provider.cache_manager import CacheManager
from src.search.content_fetcher import clear_article_content_cache
from src.search.cache_store import search_cache_store
from utils.observability import metrics_store

router = APIRouter()

VALID_CACHE_NAMESPACES = {
    "all",
    "market_data",
    "search",
    "search_response",
    "search_intel",
    "article_content",
}


def _build_cache_snapshot() -> Dict[str, Dict[str, object]]:
    """Build a consistent cache snapshot for API responses."""
    return {
        "market_data": CacheManager.get_global_cache_stats(),
        "search": search_cache_store.stats(),
    }


@router.get(
    "/metrics",
    response_model=SystemMetricsResponse,
    summary="Get runtime metrics",
    description="Return in-memory observability and cache metrics for API/Web dashboards.",
)
def get_system_metrics() -> SystemMetricsResponse:
    """Return a runtime metrics snapshot."""
    return SystemMetricsResponse(
        observability=metrics_store.snapshot(),
        observability_by_provider=metrics_store.provider_snapshot(),
        observability_trends=metrics_store.trend_snapshot(),
        recent_slowest=metrics_store.recent_slowest(),
        cache=_build_cache_snapshot(),
    )


@router.post(
    "/metrics/cache/clear",
    response_model=CacheClearResponse,
    summary="Clear runtime caches",
    description="Clear in-memory search caches or on-disk market data cache.",
)
def clear_system_metrics_cache(
    namespace: str = Query("all", description="all / market_data / search / search_response / search_intel / article_content"),
) -> CacheClearResponse:
    """Clear one or more cache namespaces."""
    normalized = (namespace or "all").strip().lower()
    if normalized not in VALID_CACHE_NAMESPACES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unsupported cache namespace: {normalized}",
                "valid_namespaces": sorted(VALID_CACHE_NAMESPACES),
            },
        )

    cleared_namespaces: List[str] = []

    if normalized in {"all", "market_data"}:
        CacheManager().clear_cache()
        CacheManager.reset_global_cache_stats()
        cleared_namespaces.append("market_data")
    if normalized in {"all", "search"}:
        search_cache_store.clear()
        cleared_namespaces.extend(["search_response", "search_intel", "article_content"])
    elif normalized in {"search_response", "search_intel"}:
        search_cache_store.clear_namespace(normalized)
        cleared_namespaces.append(normalized)
    if normalized == "article_content":
        clear_article_content_cache()
        cleared_namespaces.append("article_content")
    elif normalized == "all":
        clear_article_content_cache()

    cleared_namespaces = list(dict.fromkeys(cleared_namespaces))

    return CacheClearResponse(
        success=True,
        namespace=normalized,
        cleared_namespaces=cleared_namespaces,
        cache=_build_cache_snapshot(),
    )
