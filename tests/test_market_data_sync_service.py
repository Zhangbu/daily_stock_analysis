# -*- coding: utf-8 -*-
"""Tests for market data sync service."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from src.services.market_data_sync_service import MarketDataSyncService


class MarketDataSyncServiceTestCase(unittest.TestCase):
    def test_get_cn_universe_prioritizes_watchlist(self) -> None:
        config = SimpleNamespace(
            stock_list=["600519", "AAPL", "000001"],
            us_stock_list=[],
            market_sync_markets=["cn"],
            market_sync_a_share_full_enabled=True,
            market_sync_max_codes_per_run=0,
            market_sync_sleep_seconds=0.0,
            market_sync_historical_days=365,
            market_sync_incremental_days=5,
        )
        service = MarketDataSyncService(db_manager=MagicMock(), config=config)

        with patch.object(
            service,
            "_fetch_cn_stock_list",
            return_value=pd.DataFrame({"code": ["000001", "600519", "300750"]}),
        ), patch.object(service.stock_repo, "get_latest_trade_dates", return_value={}):
            codes = service._get_cn_universe()

        self.assertEqual(codes[:3], ["600519", "000001", "300750"])

    def test_sync_single_code_skips_when_today_already_present(self) -> None:
        service = MarketDataSyncService(db_manager=MagicMock(), config=SimpleNamespace(
            stock_list=[],
            us_stock_list=[],
            market_sync_markets=["cn"],
            market_sync_a_share_full_enabled=False,
            market_sync_max_codes_per_run=0,
            market_sync_sleep_seconds=0.0,
            market_sync_historical_days=365,
            market_sync_incremental_days=5,
        ))
        service.stock_repo.get_latest_trade_date = MagicMock(return_value=date.today())

        result = service._sync_single_code("600519")

        self.assertEqual(result, 0)

    def test_sync_single_code_fetches_incremental_window(self) -> None:
        fake_df = pd.DataFrame(
            [
                {"date": "2026-03-14", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100},
                {"date": "2026-03-15", "open": 10.5, "high": 11, "low": 10, "close": 10.8, "volume": 120},
            ]
        )
        db = MagicMock()
        db.save_daily_data.return_value = 2
        config = SimpleNamespace(
            stock_list=[],
            us_stock_list=[],
            market_sync_markets=["cn"],
            market_sync_a_share_full_enabled=False,
            market_sync_max_codes_per_run=0,
            market_sync_sleep_seconds=0.0,
            market_sync_historical_days=365,
            market_sync_incremental_days=5,
        )
        service = MarketDataSyncService(db_manager=db, config=config)
        service.stock_repo.get_latest_trade_date = MagicMock(return_value=date(2026, 3, 10))
        fake_manager = MagicMock()
        fake_manager.get_daily_data.return_value = (fake_df, "mock")

        with patch("data_provider.base.DataFetcherManager", return_value=fake_manager):
            saved = service._sync_single_code("600519")

        self.assertEqual(saved, 2)
        self.assertTrue(fake_manager.get_daily_data.called)

    def test_priority_watchlist_progress_is_tracked(self) -> None:
        config = SimpleNamespace(
            stock_list=["600519", "AAPL"],
            us_stock_list=["MSFT"],
            market_sync_markets=["cn", "us"],
            market_sync_a_share_full_enabled=False,
            market_sync_max_codes_per_run=0,
            market_sync_sleep_seconds=0.0,
            market_sync_historical_days=365,
            market_sync_incremental_days=5,
        )
        service = MarketDataSyncService(db_manager=MagicMock(), config=config)
        service._get_market_universe = MagicMock(side_effect=[["600519"], ["AAPL", "MSFT"]])
        service._sync_single_code = MagicMock(side_effect=[10, 0, 5])

        service._run_sync(["cn", "us"])

        status = service.get_status()
        self.assertEqual(status["priority_candidates"], 2)
        self.assertEqual(status["priority_processed"], 2)
        self.assertEqual(status["priority_completed"], 2)

    def test_prioritize_by_freshness_prefers_missing_then_stale(self) -> None:
        config = SimpleNamespace(
            stock_list=[],
            us_stock_list=[],
            market_sync_markets=["cn"],
            market_sync_a_share_full_enabled=False,
            market_sync_max_codes_per_run=0,
            market_sync_sleep_seconds=0.0,
            market_sync_historical_days=365,
            market_sync_incremental_days=5,
        )
        service = MarketDataSyncService(db_manager=MagicMock(), config=config)
        service.stock_repo.get_latest_trade_dates = MagicMock(
            return_value={
                "000001": date.today(),
                "600519": date.today().replace(day=max(1, date.today().day - 3)),
                "300750": None,
            }
        )

        ordered = service._prioritize_by_freshness(["000001", "600519", "300750"])

        self.assertEqual(ordered[0], "300750")
        self.assertEqual(ordered[1], "600519")


if __name__ == "__main__":
    unittest.main()
