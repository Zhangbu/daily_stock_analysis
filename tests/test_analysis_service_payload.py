# -*- coding: utf-8 -*-
"""Regression tests for AnalysisService response payload."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.services.analysis_service import AnalysisService


class AnalysisServicePayloadTestCase(unittest.TestCase):
    @patch("src.core.pipeline.StockAnalysisPipeline")
    @patch("src.config.get_config")
    def test_analyze_stock_returns_expected_payload_shape(
        self, mock_get_config, mock_pipeline_cls
    ):
        mock_get_config.return_value = SimpleNamespace()

        mock_result = SimpleNamespace(
            code="600519",
            name="贵州茅台",
            current_price=1500.0,
            change_pct=1.23,
            analysis_summary="summary",
            operation_advice="买入",
            trend_prediction="看多",
            sentiment_score=88,
            news_summary="news",
            technical_analysis="technical",
            fundamental_analysis="fundamental",
            risk_warning="risk",
            get_sniper_points=lambda: {
                "ideal_buy": 1490.0,
                "secondary_buy": 1475.0,
                "stop_loss": 1450.0,
                "take_profit": 1600.0,
            },
        )

        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.process_single_stock.return_value = mock_result

        service = AnalysisService()
        result = service.analyze_stock("600519", report_type="detailed", send_notification=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "600519")
        self.assertEqual(result["stock_name"], "贵州茅台")

        report = result["report"]
        self.assertEqual(report["meta"]["stock_code"], "600519")
        self.assertEqual(report["summary"]["operation_advice"], "买入")
        self.assertEqual(report["summary"]["sentiment_label"], "极度乐观")
        self.assertEqual(report["strategy"]["ideal_buy"], 1490.0)
        self.assertEqual(report["details"]["technical_analysis"], "technical")


if __name__ == "__main__":
    unittest.main()
