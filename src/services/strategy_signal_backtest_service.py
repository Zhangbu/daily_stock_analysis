# -*- coding: utf-8 -*-
"""Signal-driven strategy backtest service."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from backtest.engine import BacktestEngine, create_ma_signals
from strategies.strategy_loader import StrategyLoader

logger = logging.getLogger(__name__)


SignalBuilder = Callable[[pd.DataFrame], Tuple[pd.Series, pd.Series]]


class StrategySignalBacktestService:
    """Run signal-based backtests for supported technical strategies."""

    DEFAULT_LOOKBACK_DAYS = 240
    DEFAULT_INITIAL_CAPITAL = 100000.0

    def __init__(self) -> None:
        self.loader = StrategyLoader()
        self._signal_builders: Dict[str, Dict[str, Any]] = {
            "ma_golden_cross": {
                "builder": self._build_ma_golden_cross_signals,
                "profit_target": 0.15,
                "stop_loss": -0.08,
                "note": "MA5/MA20 golden cross with death cross exit.",
            },
            "volume_breakout": {
                "builder": self._build_volume_breakout_signals,
                "profit_target": 0.12,
                "stop_loss": -0.05,
                "note": "20-day resistance breakout with 2x volume confirmation.",
            },
            "shrink_pullback": {
                "builder": self._build_shrink_pullback_signals,
                "profit_target": 0.10,
                "stop_loss": -0.05,
                "note": "Bull trend pullback near MA10 with shrinking volume.",
            },
            "box_oscillation": {
                "builder": self._build_box_oscillation_signals,
                "profit_target": 0.08,
                "stop_loss": -0.04,
                "note": "Buy near 20-day support and exit near rolling resistance.",
            },
            "bottom_volume": {
                "builder": self._build_bottom_volume_signals,
                "profit_target": 0.12,
                "stop_loss": -0.06,
                "note": "Bottom reversal with large volume expansion after drawdown.",
            },
            "boll_kdj_combo": {
                "builder": self._build_boll_kdj_combo_signals,
                "profit_target": 0.10,
                "stop_loss": -0.05,
                "note": "Bollinger lower-band rebound plus low-zone KDJ crossover.",
            },
        }

    def list_strategies(self) -> List[Dict[str, Any]]:
        """Return discovered strategies with signal-backtest support metadata."""
        strategies = self.loader.discover_strategies()
        items: List[Dict[str, Any]] = []
        for strategy_id, metadata in sorted(strategies.items()):
            support_config = self._signal_builders.get(strategy_id)
            items.append(
                {
                    "id": strategy_id,
                    "name": metadata.get("display_name") or strategy_id,
                    "description": metadata.get("description") or "",
                    "category": metadata.get("category") or "uncategorized",
                    "supported": support_config is not None,
                    "support_note": (
                        support_config["note"]
                        if support_config is not None
                        else "Signal rules are not implemented yet for this YAML strategy."
                    ),
                }
            )
        return items

    def run_backtest(
        self,
        *,
        code: str,
        strategy_ids: Sequence[str],
        days: int = DEFAULT_LOOKBACK_DAYS,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ) -> Dict[str, Any]:
        """Run signal backtests for selected strategies on one stock."""
        normalized_strategy_ids = [item.strip() for item in strategy_ids if item and item.strip()]
        if not code.strip():
            raise ValueError("Stock code is required")
        if not normalized_strategy_ids:
            raise ValueError("At least one strategy is required")

        data, source = self._load_market_data(code=code.strip(), days=int(days))
        engine = BacktestEngine(initial_capital=float(initial_capital))

        results: List[Dict[str, Any]] = []
        unsupported: List[str] = []

        for strategy_id in normalized_strategy_ids:
            support_config = self._signal_builders.get(strategy_id)
            if support_config is None:
                unsupported.append(strategy_id)
                continue

            entry_signal, exit_signal = support_config["builder"](data.copy())
            backtest_result = engine.run_backtest(
                data=data,
                entry_signal=entry_signal.fillna(False),
                exit_signal=exit_signal.fillna(False),
                profit_target=support_config.get("profit_target"),
                stop_loss=support_config.get("stop_loss"),
            )
            results.append(
                {
                    "strategy_id": strategy_id,
                    "strategy_name": self._strategy_display_name(strategy_id),
                    "supported": True,
                    "note": support_config.get("note"),
                    "metrics": backtest_result.to_dict(),
                    "trades": [
                        {
                            "entry_date": trade.entry_date,
                            "entry_price": trade.entry_price,
                            "exit_date": trade.exit_date,
                            "exit_price": trade.exit_price,
                            "shares": trade.shares,
                            "profit": trade.profit,
                            "profit_pct": trade.profit_pct,
                        }
                        for trade in backtest_result.trades[:20]
                    ],
                }
            )

        return {
            "code": code.strip(),
            "data_source": source,
            "days": int(days),
            "initial_capital": float(initial_capital),
            "results": results,
            "unsupported_strategy_ids": unsupported,
        }

    def _strategy_display_name(self, strategy_id: str) -> str:
        strategy = self.loader.get_strategy(strategy_id) or {}
        return str(strategy.get("display_name") or strategy.get("name") or strategy_id)

    def _load_market_data(self, *, code: str, days: int) -> Tuple[pd.DataFrame, str]:
        from data_provider.base import DataFetcherManager

        manager = DataFetcherManager()
        df, source = manager.get_daily_data(code, days=days)
        if df is None or df.empty:
            raise ValueError(f"No market data available for {code}")

        normalized = df.copy()
        if "date" not in normalized.columns:
            normalized = normalized.reset_index()
        required_columns = ["date", "open", "high", "low", "close"]
        missing = [column for column in required_columns if column not in normalized.columns]
        if missing:
            raise ValueError(f"Market data missing required columns: {missing}")
        if "volume" not in normalized.columns:
            normalized["volume"] = 0.0

        normalized["date"] = pd.to_datetime(normalized["date"])
        normalized = normalized.sort_values("date").reset_index(drop=True)
        return normalized, str(source or "unknown")

    @staticmethod
    def _build_ma_golden_cross_signals(data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        return create_ma_signals(data, short_period=5, long_period=20)

    @staticmethod
    def _build_volume_breakout_signals(data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        volume_ma5 = data["volume"].rolling(window=5).mean()
        resistance = data["high"].rolling(window=20).max().shift(1)
        ma10 = data["close"].rolling(window=10).mean()
        entry = (data["close"] > resistance) & (data["volume"] > volume_ma5 * 2)
        exit_signal = (data["close"] < ma10) | (data["close"] < data["low"].rolling(window=10).min().shift(1))
        return entry.fillna(False), exit_signal.fillna(False)

    @staticmethod
    def _build_shrink_pullback_signals(data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        ma5 = data["close"].rolling(window=5).mean()
        ma10 = data["close"].rolling(window=10).mean()
        ma20 = data["close"].rolling(window=20).mean()
        volume_ma5 = data["volume"].rolling(window=5).mean()
        trend_ok = (ma5 > ma10) & (ma10 > ma20)
        near_ma10 = ((data["close"] - ma10).abs() / ma10) <= 0.02
        entry = trend_ok & near_ma10 & (data["volume"] < volume_ma5 * 0.7) & (data["close"] >= ma10)
        exit_signal = (data["close"] < ma20) | (ma5 < ma10)
        return entry.fillna(False), exit_signal.fillna(False)

    @staticmethod
    def _build_box_oscillation_signals(data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        support = data["low"].rolling(window=20).min().shift(1)
        resistance = data["high"].rolling(window=20).max().shift(1)
        box_width_ok = ((resistance - support) / support) >= 0.05
        entry = box_width_ok & (data["close"] <= support * 1.03)
        exit_signal = box_width_ok & (data["close"] >= resistance * 0.97)
        return entry.fillna(False), exit_signal.fillna(False)

    @staticmethod
    def _build_bottom_volume_signals(data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        rolling_high20 = data["high"].rolling(window=20).max().shift(1)
        rolling_low20 = data["low"].rolling(window=20).min().shift(1)
        volume_ma5 = data["volume"].rolling(window=5).mean()
        ma20 = data["close"].rolling(window=20).mean()
        drawdown = (rolling_high20 - data["close"]) / rolling_high20
        entry = (
            (drawdown >= 0.15)
            & (data["close"] <= rolling_low20 * 1.05)
            & (data["volume"] > volume_ma5 * 3)
            & (data["close"] > data["open"])
        )
        exit_signal = (data["close"] >= ma20) | (data["close"] >= rolling_high20 * 0.95)
        return entry.fillna(False), exit_signal.fillna(False)

    @staticmethod
    def _build_boll_kdj_combo_signals(data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        mid = data["close"].rolling(window=20).mean()
        std = data["close"].rolling(window=20).std()
        upper = mid + 2 * std
        lower = mid - 2 * std

        low_n = data["low"].rolling(window=9).min()
        high_n = data["high"].rolling(window=9).max()
        rsv = ((data["close"] - low_n) / (high_n - low_n).replace(0, pd.NA)) * 100
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()

        golden_cross = (k > d) & (k.shift(1) <= d.shift(1))
        death_cross = (k < d) & (k.shift(1) >= d.shift(1))

        entry = ((data["close"] <= lower * 1.02) & (k < 20) & (d < 20)) | (
            (data["close"] <= lower * 1.05) & golden_cross & (k < 30)
        )
        exit_signal = ((data["close"] >= upper * 0.98) & (k > 80) & (d > 80)) | death_cross
        return entry.fillna(False), exit_signal.fillna(False)
