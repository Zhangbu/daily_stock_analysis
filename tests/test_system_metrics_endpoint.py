# -*- coding: utf-8 -*-
"""Tests for system metrics endpoint snapshot."""

import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api.v1.endpoints.system_metrics import clear_system_metrics_cache, get_system_metrics
from data_provider.cache_manager import CacheManager
from src.search.cache_store import search_cache_store
from utils.observability import metrics_store


class SystemMetricsEndpointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        metrics_store.clear()
        search_cache_store.clear()
        CacheManager.reset_global_cache_stats()

    def test_get_system_metrics_returns_observability_and_cache(self):
        metrics_store.record(operation="demo", status="ok", duration_ms=12, cache_hit=True)
        search_cache_store.put("search_response", "demo", {"value": True})

        payload = get_system_metrics()

        self.assertIn("demo", payload.observability)
        self.assertIn("p50_duration_ms", payload.observability["demo"])
        self.assertIn("p95_duration_ms", payload.observability["demo"])
        self.assertIn("demo", payload.observability_trends)
        self.assertGreaterEqual(payload.observability_trends["demo"][0].p50_duration_ms, 0)
        self.assertGreaterEqual(payload.observability_trends["demo"][0].p95_duration_ms, 0)
        self.assertIsInstance(payload.observability_by_provider, dict)
        self.assertIsInstance(payload.recent_slowest, list)
        self.assertIn("market_data", payload.cache)
        self.assertIn("search", payload.cache)

    def test_clear_system_metrics_cache_clears_selected_namespace(self):
        search_cache_store.put("search_response", "demo", {"value": True})

        payload = clear_system_metrics_cache("search_response")

        self.assertTrue(payload.success)
        self.assertEqual(payload.cleared_namespaces, ["search_response"])
        self.assertIsNone(search_cache_store.get("search_response", "demo", 60))

    def test_clear_system_metrics_cache_clears_market_data_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CacheManager(cache_dir=temp_dir, ttl_seconds=60)
            with patch("api.v1.endpoints.system_metrics.CacheManager", return_value=cache), patch(
                "api.v1.endpoints.system_metrics.CacheManager.get_global_cache_stats",
                return_value={},
            ), patch(
                "api.v1.endpoints.system_metrics.CacheManager.reset_global_cache_stats",
            ):
                result = clear_system_metrics_cache("market_data")
            self.assertTrue(result.success)
            self.assertEqual(result.cleared_namespaces, ["market_data"])

    def test_clear_system_metrics_cache_supports_grouped_search_namespace(self):
        search_cache_store.put("search_response", "demo-1", {"value": True})
        search_cache_store.put("search_intel", "demo-2", {"value": True})
        search_cache_store.put("article_content", "demo-3", {"value": True})

        payload = clear_system_metrics_cache("search")

        self.assertTrue(payload.success)
        self.assertEqual(payload.cleared_namespaces, ["search_response", "search_intel", "article_content"])
        self.assertEqual(payload.cache["search"], {})

    def test_clear_system_metrics_cache_rejects_invalid_namespace(self):
        with self.assertRaises(HTTPException) as context:
            clear_system_metrics_cache("invalid")

        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
