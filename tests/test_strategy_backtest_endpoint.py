# -*- coding: utf-8 -*-
"""Tests for signal strategy backtest endpoints."""

import unittest
from unittest.mock import patch

from api.v1.endpoints.strategy_backtest import get_signal_backtest_strategies, run_signal_strategy_backtest
from api.v1.schemas.strategy_backtest import StrategySignalBacktestRunRequest


class StrategyBacktestEndpointTestCase(unittest.TestCase):
    def test_get_signal_backtest_strategies_returns_payload(self) -> None:
        with patch("api.v1.endpoints.strategy_backtest.StrategySignalBacktestService") as service_cls:
            service_cls.return_value.list_strategies.return_value = [
                {
                    "id": "ma_golden_cross",
                    "name": "均线金叉",
                    "description": "desc",
                    "category": "trend",
                    "supported": True,
                    "support_note": "note",
                }
            ]
            payload = get_signal_backtest_strategies()

        self.assertEqual(len(payload.strategies), 1)
        self.assertEqual(payload.strategies[0].id, "ma_golden_cross")

    def test_run_signal_strategy_backtest_returns_response(self) -> None:
        with patch("api.v1.endpoints.strategy_backtest.StrategySignalBacktestService") as service_cls:
            service_cls.return_value.run_backtest.return_value = {
                "code": "600519",
                "data_source": "mock",
                "days": 240,
                "initial_capital": 100000.0,
                "unsupported_strategy_ids": [],
                "results": [
                    {
                        "strategy_id": "ma_golden_cross",
                        "strategy_name": "均线金叉",
                        "supported": True,
                        "note": "note",
                        "metrics": {
                            "total_trades": 1,
                            "winning_trades": 1,
                            "losing_trades": 0,
                            "win_rate": 1.0,
                            "avg_profit": 1000.0,
                            "avg_win": 1000.0,
                            "avg_loss": 0.0,
                            "avg_profit_pct": 0.05,
                            "total_profit": 1000.0,
                            "total_profit_pct": 1.0,
                            "max_drawdown": 500.0,
                            "max_drawdown_pct": 0.03,
                            "sharpe_ratio": 1.2,
                        },
                        "trades": [],
                    }
                ],
            }
            payload = run_signal_strategy_backtest(
                StrategySignalBacktestRunRequest(code="600519", strategy_ids=["ma_golden_cross"])
            )

        self.assertEqual(payload.code, "600519")
        self.assertEqual(payload.results[0].strategy_id, "ma_golden_cross")


if __name__ == "__main__":
    unittest.main()
