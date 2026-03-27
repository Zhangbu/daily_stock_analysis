# -*- coding: utf-8 -*-
"""Tests for observability helpers."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from utils.observability import InMemoryMetricsStore, OperationTimer


class ObservabilityTestCase(unittest.TestCase):
    def test_operation_timer_records_success_metric(self):
        logger = Mock()
        store = InMemoryMetricsStore()

        with OperationTimer(logger, "demo_operation", metric_store=store, cache_hit=True) as timer:
            timer.set_message("done")

        snapshot = store.snapshot()
        self.assertEqual(snapshot["demo_operation"]["count"], 1)
        self.assertEqual(snapshot["demo_operation"]["success"], 1)
        self.assertEqual(snapshot["demo_operation"]["cache_hits"], 1)

    def test_operation_timer_marks_handled_failure(self):
        logger = Mock()
        store = InMemoryMetricsStore()

        with OperationTimer(logger, "failing_operation", metric_store=store) as timer:
            timer.mark_failed("failed")

        snapshot = store.snapshot()
        self.assertEqual(snapshot["failing_operation"]["error"], 1)

    def test_provider_snapshot_and_recent_slowest_are_recorded(self):
        logger = Mock()
        store = InMemoryMetricsStore()

        with OperationTimer(logger, "provider_operation", metric_store=store, provider="search_api") as timer:
            timer.set_message("ok")

        provider_snapshot = store.provider_snapshot()
        self.assertIn("provider_operation:search_api", provider_snapshot)
        self.assertEqual(provider_snapshot["provider_operation:search_api"]["count"], 1)
        self.assertIn("p50_duration_ms", provider_snapshot["provider_operation:search_api"])
        self.assertIn("p95_duration_ms", provider_snapshot["provider_operation:search_api"])
        self.assertEqual(store.recent_slowest(limit=1)[0]["operation"], "provider_operation")

    def test_trend_snapshot_groups_events_by_bucket(self):
        logger = Mock()
        store = InMemoryMetricsStore()

        with patch("utils.observability.time.time", side_effect=[100.0, 130.0]):
            with OperationTimer(logger, "trend_operation", metric_store=store, cache_hit=True):
                pass
            with OperationTimer(logger, "trend_operation", metric_store=store, cache_hit=False):
                pass

        trends = store.trend_snapshot()
        self.assertIn("trend_operation", trends)
        self.assertEqual(len(trends["trend_operation"]), 2)
        self.assertEqual(trends["trend_operation"][0]["bucket_ts"], 60)
        self.assertEqual(trends["trend_operation"][1]["bucket_ts"], 120)
        self.assertIn("p50_duration_ms", trends["trend_operation"][0])
        self.assertIn("p95_duration_ms", trends["trend_operation"][0])

    def test_snapshot_contains_latency_percentiles(self):
        logger = Mock()
        store = InMemoryMetricsStore()

        with OperationTimer(logger, "percentile_operation", metric_store=store):
            pass
        with OperationTimer(logger, "percentile_operation", metric_store=store):
            pass

        snapshot = store.snapshot()
        self.assertIn("p50_duration_ms", snapshot["percentile_operation"])
        self.assertIn("p95_duration_ms", snapshot["percentile_operation"])


if __name__ == "__main__":
    unittest.main()
