# -*- coding: utf-8 -*-
"""Tests for database-mode screening."""

import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from src.services.screening_service import ScreeningService


def _make_history(code: str, closes: list[float], volumes: list[float]):
    start = date(2026, 1, 1)
    items = []
    for idx, close in enumerate(closes):
        items.append(
            SimpleNamespace(
                code=code,
                date=start + timedelta(days=idx),
                close=close,
                volume=volumes[idx],
                amount=volumes[idx] * close,
                pct_chg=0.5,
                ma5=None,
                ma10=None,
                ma20=None,
            )
        )
    return items


class ScreeningServiceDatabaseModeTestCase(unittest.TestCase):
    def test_database_mode_returns_ranked_candidates(self) -> None:
        service = ScreeningService()
        service.stock_repo.get_latest_snapshots = lambda: [
            SimpleNamespace(code="600519", close=120, amount=300_000_000, volume=2_000_000, pct_chg=2.5),
            SimpleNamespace(code="AAPL", close=210, amount=500_000_000, volume=3_000_000, pct_chg=1.8),
        ]
        service.stock_repo.get_latest = lambda code, days=60: (
            _make_history(
                code,
                closes=[80 + i * 0.8 for i in range(60)] if code == "600519" else [150 + i * 1.2 for i in range(60)],
                volumes=[100_000] * 59 + [250_000],
            )
        )

        result = service.screen_stocks(
            market="cn",
            data_mode="database",
            min_turnover=100_000_000,
            target_count=10,
        )

        self.assertEqual(result["summary"]["market"], "cn")
        self.assertEqual(result["summary"]["data_mode"], "database")
        self.assertEqual(len(result["stocks"]), 1)
        self.assertEqual(result["stocks"][0]["code"], "600519")
        self.assertIsNotNone(result["stocks"][0]["score"])
        self.assertEqual(result["stocks"][0]["rank"], 1)
        self.assertIn(result["stocks"][0]["opportunity_tier"], {"A", "S"})
        self.assertIn("trend", result["stocks"][0]["score_breakdown"])
        self.assertIn("risk", result["stocks"][0]["score_breakdown"])
        self.assertIn("consistency", result["stocks"][0]["score_breakdown"])
        self.assertEqual(result["summary"]["top_candidates"], ["600519"])
        self.assertGreater(result["summary"]["top_score"], 0)


if __name__ == "__main__":
    unittest.main()
