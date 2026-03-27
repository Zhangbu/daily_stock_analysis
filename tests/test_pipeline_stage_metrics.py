# -*- coding: utf-8 -*-
"""Unit tests for pipeline stage latency metrics emission."""

import time
import unittest
from unittest.mock import patch

from src.core.pipeline import StockAnalysisPipeline


class PipelineStageMetricsTestCase(unittest.TestCase):
    def test_log_stage_latency_records_metric(self) -> None:
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        started_at = time.perf_counter() - 0.02

        with patch("src.core.analysis_quality.metrics_store.record") as record_mock:
            pipeline._log_stage_latency(code="600519", stage_name="trend", started_at=started_at)

        record_mock.assert_called_once()
        kwargs = record_mock.call_args.kwargs
        self.assertEqual(kwargs["operation"], "pipeline_stage_trend")
        self.assertEqual(kwargs["status"], "ok")
        self.assertIsInstance(kwargs["duration_ms"], int)
        self.assertGreaterEqual(kwargs["duration_ms"], 0)


if __name__ == "__main__":
    unittest.main()
