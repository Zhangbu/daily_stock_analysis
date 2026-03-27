# -*- coding: utf-8 -*-
"""Fault-tolerance regression tests for pipeline critical paths."""

from datetime import date, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from src.analyzer import AnalysisResult
from src.core.pipeline import StockAnalysisPipeline
from src.enums import ReportType


def _make_result(
    *,
    advice: str = "买入",
    decision_type: str = "buy",
    confidence: str = "高",
    score: int = 82,
) -> AnalysisResult:
    return AnalysisResult(
        code="600519",
        name="贵州茅台",
        sentiment_score=score,
        trend_prediction="看多",
        operation_advice=advice,
        decision_type=decision_type,
        confidence_level=confidence,
        analysis_summary="原始摘要",
        risk_warning="原始风险",
    )


class PipelineFaultToleranceTestCase(unittest.TestCase):
    def test_process_single_stock_downgrades_on_fetch_failure_with_stale_data(self) -> None:
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.config = SimpleNamespace(analysis_stale_days_limit=2)
        pipeline.query_id = None
        pipeline.notifier = Mock()
        pipeline.notifier.is_available.return_value = False
        pipeline.fetch_and_save_stock_data = Mock(return_value=(False, "network failed"))
        pipeline.analyze_stock = Mock(return_value=_make_result(score=75))
        pipeline.persistence = Mock()
        pipeline.persistence.get_analysis_context.return_value = {
            "date": (date.today() - timedelta(days=3)).isoformat()
        }

        result = pipeline.process_single_stock(
            code="600519",
            skip_analysis=False,
            single_stock_notify=False,
            report_type=ReportType.SIMPLE,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.operation_advice, "观望")
        self.assertEqual(result.decision_type, "hold")
        self.assertEqual(result.confidence_level, "低")
        self.assertIn("数据非最新", result.analysis_summary)

    def test_collect_parallel_inputs_tolerates_intel_failure(self) -> None:
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.config = SimpleNamespace(enable_realtime_quote=False, analysis_stale_days_limit=2)
        trend_sentinel = object()
        pipeline._build_trend_result = Mock(return_value=trend_sentinel)
        pipeline.intel_coordinator = Mock()
        pipeline.intel_coordinator.collect_comprehensive_intel.side_effect = RuntimeError("intel down")

        trend_result, news_context = pipeline._collect_parallel_analysis_inputs(
            code="600519",
            stock_name="贵州茅台",
            query_id="q1",
            realtime_quote=None,
        )

        self.assertIs(trend_result, trend_sentinel)
        self.assertEqual(news_context, "")

    def test_standard_engine_returns_result_with_low_confidence_when_trend_and_intel_missing(self) -> None:
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.config = SimpleNamespace(enable_realtime_quote=False, analysis_stale_days_limit=2)
        pipeline.persistence = Mock()
        pipeline.persistence.get_analysis_context.return_value = {
            "code": "600519",
            "date": date.today().isoformat(),
            "today": {"close": 10.5},
            "yesterday": {"close": 10.2},
        }
        pipeline.persistence.build_context_snapshot.return_value = {}
        pipeline.persistence.save_analysis_history = Mock()
        pipeline.analyzer = Mock()
        pipeline.analyzer.analyze.return_value = _make_result(confidence="高")
        pipeline._collect_parallel_analysis_inputs = Mock(return_value=(None, ""))

        result = pipeline._analyze_with_standard_engine(
            code="600519",
            report_type=ReportType.SIMPLE,
            query_id="q1",
            stock_name="贵州茅台",
            realtime_quote=None,
            chip_data=None,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.confidence_level, "低")
        self.assertIn("关键分析维度缺失", result.risk_warning)


if __name__ == "__main__":
    unittest.main()
