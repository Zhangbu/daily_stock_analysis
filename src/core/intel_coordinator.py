# -*- coding: utf-8 -*-
"""Intel orchestration helpers extracted from the stock analysis pipeline."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class IntelCoordinator:
    """Coordinate intel search, formatting, and persistence."""

    def __init__(
        self,
        *,
        search_service,
        persistence,
        build_query_context: Callable[..., Dict[str, str]],
        query_cache_ttl_seconds: int = 300,
    ) -> None:
        self.search_service = search_service
        self.persistence = persistence
        self.build_query_context = build_query_context
        self._query_cache_ttl_seconds = max(0, int(query_cache_ttl_seconds))
        self._query_cache_lock = threading.Lock()
        self._query_cache: Dict[str, tuple] = {}

    def _cache_get(self, key: str):
        """Return query-scoped cached value when not expired."""
        if self._query_cache_ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with self._query_cache_lock:
            item = self._query_cache.get(key)
            if item is None:
                return None
            expires_at, value = item
            if now >= expires_at:
                self._query_cache.pop(key, None)
                return None
            return value

    def _cache_put(self, key: str, value) -> None:
        """Store query-scoped short-lived cache item."""
        if self._query_cache_ttl_seconds <= 0:
            return
        expires_at = time.monotonic() + self._query_cache_ttl_seconds
        with self._query_cache_lock:
            self._query_cache[key] = (expires_at, value)

    def collect_comprehensive_intel(
        self,
        *,
        code: str,
        stock_name: str,
        query_id: str,
        max_searches: int = 5,
    ) -> Optional[str]:
        """Collect and persist comprehensive intel, then return formatted context."""
        if not self.search_service.is_available:
            logger.info(f"[{code}] 搜索服务不可用，跳过情报搜索")
            return None

        cache_key = f"comprehensive:{query_id}:{code}:{stock_name}:{max_searches}"
        cached_news_context = self._cache_get(cache_key)
        if cached_news_context is not None:
            logger.info(f"[{code}] 命中查询级情报缓存，跳过重复搜索")
            return cached_news_context

        logger.info(f"[{code}] 开始多维度情报搜索...")
        intel_results = self.search_service.search_comprehensive_intel(
            stock_code=code,
            stock_name=stock_name,
            max_searches=max_searches,
        )

        if not intel_results:
            return None

        news_context = self.search_service.format_intel_report(intel_results, stock_name)
        total_results = sum(len(r.results) for r in intel_results.values() if r.success)
        logger.info(f"[{code}] 情报搜索完成: 共 {total_results} 条结果")
        logger.debug(f"[{code}] 情报搜索结果:\n{news_context}")

        try:
            query_context = self.build_query_context(query_id=query_id)
            for dim_name, response in intel_results.items():
                if response and response.success and response.results:
                    self.persistence.save_news_intel(
                        code=code,
                        name=stock_name,
                        dimension=dim_name,
                        query=response.query,
                        response=response,
                        query_context=query_context,
                    )
        except Exception as exc:
            logger.warning(f"[{code}] 保存新闻情报失败: {exc}")

        self._cache_put(cache_key, news_context)
        return news_context

    def persist_latest_news_for_agent(
        self,
        *,
        code: str,
        stock_name: str,
        query_id: str,
        max_results: int = 5,
    ) -> None:
        """Persist latest news used by the agent analysis flow."""
        if not self.search_service.is_available:
            return

        cache_key = f"agent_latest_news:{query_id}:{code}:{stock_name}:{max_results}"
        if self._cache_get(cache_key):
            logger.info(f"[{code}] Agent 模式命中查询级新闻缓存，跳过重复保存")
            return

        try:
            news_response = self.search_service.search_stock_news(
                stock_code=code,
                stock_name=stock_name,
                max_results=max_results,
            )
            if news_response.success and news_response.results:
                query_context = self.build_query_context(query_id=query_id)
                self.persistence.save_news_intel(
                    code=code,
                    name=stock_name,
                    dimension="latest_news",
                    query=news_response.query,
                    response=news_response,
                    query_context=query_context,
                )
                logger.info(f"[{code}] Agent 模式: 新闻情报已保存 {len(news_response.results)} 条")
                self._cache_put(cache_key, True)
        except Exception as exc:
            logger.warning(f"[{code}] Agent 模式保存新闻情报失败: {exc}")
