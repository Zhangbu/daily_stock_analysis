# -*- coding: utf-8 -*-
"""Unit tests for pipeline guard logic."""

import unittest
from types import SimpleNamespace

from src.analyzer import AnalysisResult
from src.core.pipeline import StockAnalysisPipeline


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


class PipelineGuardsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        self.pipeline.config = SimpleNamespace(analysis_stale_days_limit=2)

    def test_stale_data_guard_downgrades_when_age_exceeds_limit(self) -> None:
        result = _make_result()
        self.pipeline._apply_stale_data_guard(
            result=result,
            code="600519",
            data_age_days=3,
            fetch_success=True,
        )
        self.assertEqual(result.operation_advice, "观望")
        self.assertEqual(result.decision_type, "hold")
        self.assertEqual(result.confidence_level, "低")
        self.assertLessEqual(result.sentiment_score, 60)
        self.assertIn("数据非最新", result.analysis_summary)

    def test_stale_data_guard_downgrades_when_fetch_failed_with_old_data(self) -> None:
        result = _make_result(score=70)
        self.pipeline._apply_stale_data_guard(
            result=result,
            code="600519",
            data_age_days=1,
            fetch_success=False,
        )
        self.assertEqual(result.operation_advice, "观望")
        self.assertEqual(result.decision_type, "hold")
        self.assertEqual(result.confidence_level, "低")

    def test_stale_data_guard_keeps_result_when_data_fresh(self) -> None:
        result = _make_result()
        self.pipeline._apply_stale_data_guard(
            result=result,
            code="600519",
            data_age_days=0,
            fetch_success=True,
        )
        self.assertEqual(result.operation_advice, "买入")
        self.assertEqual(result.decision_type, "buy")
        self.assertEqual(result.confidence_level, "高")

    def test_data_completeness_guard_force_hold_when_history_and_realtime_missing(self) -> None:
        result = _make_result()
        self.pipeline._apply_data_completeness_guard(
            result=result,
            code="600519",
            context={"data_missing": True},
            trend_result=None,
            news_context="",
            realtime_quote=None,
        )
        self.assertEqual(result.operation_advice, "观望")
        self.assertEqual(result.decision_type, "hold")
        self.assertEqual(result.confidence_level, "低")
        self.assertIn("历史与实时行情均缺失", result.risk_warning)

    def test_data_completeness_guard_reduces_high_confidence_on_single_dimension_missing(self) -> None:
        result = _make_result(confidence="高")
        self.pipeline._apply_data_completeness_guard(
            result=result,
            code="600519",
            context={"data_missing": False},
            trend_result=None,
            news_context="有新闻",
            realtime_quote=SimpleNamespace(price=10.5),
        )
        self.assertEqual(result.confidence_level, "中")
        self.assertIn("关键分析维度缺失", result.risk_warning)

    def test_data_completeness_guard_sets_low_confidence_when_two_dimensions_missing(self) -> None:
        result = _make_result(confidence="中")
        self.pipeline._apply_data_completeness_guard(
            result=result,
            code="600519",
            context={"data_missing": False},
            trend_result=None,
            news_context="",
            realtime_quote=SimpleNamespace(price=12.3),
        )
        self.assertEqual(result.confidence_level, "低")

    def test_get_data_age_days_prefers_context_date_hint(self) -> None:
        self.pipeline.persistence = SimpleNamespace(
            get_analysis_context=lambda code: {"date": "1900-01-01"}
        )
        age_days = self.pipeline._get_data_age_days("600519", context_date_hint="2099-01-01")
        self.assertEqual(age_days, 0)


if __name__ == "__main__":
    unittest.main()
