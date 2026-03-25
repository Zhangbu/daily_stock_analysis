# -*- coding: utf-8 -*-
"""Tests for shared search cache metrics and behavior."""

import unittest

from src.search.cache_store import search_cache_store


class SearchCacheStoreTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        search_cache_store.clear()

    def test_namespace_stats_include_hit_rate(self):
        search_cache_store.put("search_response", "k1", {"ok": True})
        self.assertEqual(search_cache_store.get("search_response", "k1", 60), {"ok": True})
        self.assertIsNone(search_cache_store.get("search_response", "missing", 60))

        stats = search_cache_store.stats()["search_response"]
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate_pct"], 50)

    def test_clear_namespace_only_removes_target_namespace(self):
        search_cache_store.put("search_response", "k1", 1)
        search_cache_store.put("article_content", "k2", 2)

        search_cache_store.clear_namespace("article_content")

        self.assertEqual(search_cache_store.get("search_response", "k1", 60), 1)
        self.assertIsNone(search_cache_store.stats().get("article_content"))


if __name__ == "__main__":
    unittest.main()
