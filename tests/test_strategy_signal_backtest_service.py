# -*- coding: utf-8 -*-
"""Tests for signal-based strategy backtest service."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.services.strategy_signal_backtest_service import StrategySignalBacktestService


def _sample_market_data() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    close = []
    for idx in range(80):
        if idx < 20:
            close.append(100 - idx * 0.4)
        elif idx < 45:
            close.append(92 + (idx - 20) * 0.8)
        elif idx < 60:
            close.append(112 - (idx - 45) * 0.6)
        else:
            close.append(103 + (idx - 60) * 0.9)
    frame = pd.DataFrame({"date": dates, "close": close})
    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    frame["high"] = frame[["open", "close"]].max(axis=1) + 1.2
    frame["low"] = frame[["open", "close"]].min(axis=1) - 1.2
    frame["volume"] = 1000
    frame.loc[42, "volume"] = 4000
    frame.loc[65, "volume"] = 4500
    return frame


class StrategySignalBacktestServiceTestCase(unittest.TestCase):
    def test_list_strategies_marks_supported_and_pending(self) -> None:
        service = StrategySignalBacktestService()

        strategies = service.list_strategies()
        strategy_map = {item["id"]: item for item in strategies}

        self.assertTrue(strategy_map["ma_golden_cross"]["supported"])
        self.assertFalse(strategy_map["wave_theory"]["supported"])

    def test_run_backtest_returns_metrics_for_supported_strategies(self) -> None:
        service = StrategySignalBacktestService()
        fake_manager = MagicMock()
        fake_manager.get_daily_data.return_value = (_sample_market_data(), "mock")

        with patch("data_provider.base.DataFetcherManager", return_value=fake_manager):
            payload = service.run_backtest(
                code="600519",
                strategy_ids=["ma_golden_cross", "volume_breakout"],
                days=120,
                initial_capital=50000,
            )

        self.assertEqual(payload["code"], "600519")
        self.assertEqual(payload["data_source"], "mock")
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["unsupported_strategy_ids"], [])
        self.assertIn("metrics", payload["results"][0])


if __name__ == "__main__":
    unittest.main()
