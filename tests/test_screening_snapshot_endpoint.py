# -*- coding: utf-8 -*-
"""Tests for screening snapshot endpoints."""

import unittest
from unittest.mock import patch

from api.v1.endpoints.screening import get_top_analysis_summary, list_screening_snapshots, save_screening_snapshot
from api.v1.schemas.screening import (
    ScreeningSnapshotSaveRequest,
    ScreeningTopAnalysisSummaryRequest,
    StockInfo,
    StockScreeningRequest,
    StockScreeningSummary,
)


class ScreeningSnapshotEndpointTestCase(unittest.TestCase):
    def test_save_snapshot_returns_success(self) -> None:
        request = ScreeningSnapshotSaveRequest(
            filters=StockScreeningRequest(market="cn", data_mode="database"),
            summary=StockScreeningSummary(
                count=1,
                avg_market_cap=0,
                avg_turnover=0,
                avg_turnover_rate=0,
                avg_price=10,
                avg_change_pct=1,
                market="cn",
                data_mode="database",
                top_score=88,
                avg_score=88,
                top_candidates=["600519"],
            ),
            stocks=[
                StockInfo(
                    code="600519",
                    name="600519",
                    price=10,
                    market_cap=0,
                    turnover=0,
                    turnover_rate=0,
                    change_pct=1,
                )
            ],
        )

        with patch("api.v1.endpoints.screening.ScreeningSnapshotRepository") as repo_cls:
            repo_cls.return_value.save_snapshot.return_value = 7
            payload = save_screening_snapshot(request)

        self.assertTrue(payload.success)
        self.assertEqual(payload.record_id, 7)

    def test_list_snapshots_returns_items(self) -> None:
        fake_row = type(
            "Row",
            (),
            {
                "snapshot_id": "snap_001",
                "market": "cn",
                "data_mode": "database",
                "created_at": None,
                "summary_json": '{"top_candidates":["600519"],"top_score":88}',
                "candidates_json": '[{"code":"600519","price":100}]',
            },
        )()
        fake_latest = type("Latest", (), {"code": "600519", "close": 110})()
        with patch("api.v1.endpoints.screening.ScreeningSnapshotRepository") as repo_cls, patch("api.v1.endpoints.screening.StockRepository") as stock_repo_cls:
            repo_cls.return_value.get_recent.return_value = [fake_row]
            stock_repo_cls.return_value.get_latest_snapshots.return_value = [fake_latest]
            payload = list_screening_snapshots(limit=5)

        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0].snapshot_id, "snap_001")
        self.assertEqual(payload.items[0].performance_summary["avg_return_pct"], 10.0)

    def test_top_analysis_summary_returns_latest_items(self) -> None:
        fake_analysis = type(
            "Analysis",
            (),
            {
                "code": "600519",
                "name": "贵州茅台",
                "operation_advice": "买入",
                "trend_prediction": "看多",
                "sentiment_score": 82,
                "analysis_summary": "趋势保持完好",
                "created_at": None,
            },
        )()
        with patch("api.v1.endpoints.screening.AnalysisRepository") as repo_cls:
            repo_cls.return_value.get_latest_by_codes.return_value = {"600519": fake_analysis}
            payload = get_top_analysis_summary(ScreeningTopAnalysisSummaryRequest(codes=["600519"]))

        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0].code, "600519")
        self.assertEqual(payload.items[0].operation_advice, "买入")


if __name__ == "__main__":
    unittest.main()
