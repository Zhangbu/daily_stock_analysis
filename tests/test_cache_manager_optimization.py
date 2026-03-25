# -*- coding: utf-8 -*-
"""Tests for cache manager TTL and stats improvements."""

import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta

import pandas as pd

from data_provider.cache_manager import CacheManager


class CacheManagerOptimizationTestCase(unittest.TestCase):
    def test_cache_hit_updates_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CacheManager(cache_dir=temp_dir, cache_format="parquet", ttl_seconds=60)
            start_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
            sample = pd.DataFrame(
                {
                    "date": pd.date_range(start_date, periods=3),
                    "close": [1.0, 2.0, 3.0],
                }
            )
            cache.save_data("600519", sample)

            result = cache.get_cached_data("600519", start_date, datetime.now().strftime("%Y-%m-%d"))

            self.assertIsNotNone(result)
            self.assertEqual(cache.get_cache_stats()["hits"], 1)
            self.assertEqual(cache.get_cache_stats()["writes"], 1)

    def test_cache_ttl_marks_file_as_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CacheManager(cache_dir=temp_dir, cache_format="parquet", ttl_seconds=1)
            sample = pd.DataFrame(
                {
                    "date": pd.date_range("2024-01-01", periods=2),
                    "close": [1.0, 2.0],
                }
            )
            cache.save_data("600519", sample)
            cache_file = os.path.join(temp_dir, "600519.parquet")
            old_ts = time.time() - 120
            os.utime(cache_file, (old_ts, old_ts))

            result = cache.get_cached_data("600519", "2024-01-01", "2024-01-02")

            self.assertIsNone(result)
            self.assertEqual(cache.get_cache_stats()["stale"], 1)


if __name__ == "__main__":
    unittest.main()
