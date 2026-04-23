# -*- coding: utf-8 -*-
"""
Profile strategy backtest service for US profile workflows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd

from src.services.profile_stock_metadata import get_profile_stock_metadata
from src.services.profile_strategy_service import ProfileStrategyService


logger = logging.getLogger(__name__)


@dataclass
class ProfileBacktestItem:
    code: str
    stock_name: str
    analysis_date: date
    entry_date: date
    exit_date: date
    score: int
    grade: str
    verdict: str
    entry_price: float
    exit_price: float
    max_return_pct: float
    min_return_pct: float
    window_return_pct: float
    outcome: str


class ProfileStrategyBacktestService:
    """Run on-the-fly backtests for profile-based executable strategies."""

    def __init__(self, profile_name: str, strategy_name: str):
        self.profile_service = ProfileStrategyService(profile_name=profile_name, strategy_name=strategy_name)
        self.neutral_band_pct = 1.0
        self.warmup_bars = 60

    def run(
        self,
        *,
        stock_codes: Optional[List[str]] = None,
        analysis_date_from: Optional[date] = None,
        analysis_date_to: Optional[date] = None,
        eval_window_days: int = 10,
        only_passed: bool = True,
    ) -> Dict[str, object]:
        items: List[ProfileBacktestItem] = []
        resolved_codes = self.profile_service.resolve_stock_codes(stock_codes)

        for code in resolved_codes:
            df = self.profile_service.load_daily_data(code).copy()
            if df.empty or len(df) <= self.warmup_bars + eval_window_days:
                continue

            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
            stock_items = self._run_single_code(
                code=code,
                df=df,
                analysis_date_from=analysis_date_from,
                analysis_date_to=analysis_date_to,
                eval_window_days=eval_window_days,
                only_passed=only_passed,
            )
            items.extend(stock_items)

        items.sort(key=lambda item: (item.analysis_date, item.score), reverse=True)
        summary = self._build_summary(items, eval_window_days)

        return {
            "profile_name": self.profile_service.profile.name,
            "strategy_name": self.profile_service.strategy.name,
            "display_name": self.profile_service.strategy.display_name,
            "eval_window_days": eval_window_days,
            "items": items,
            "summary": summary,
        }

    def _run_single_code(
        self,
        *,
        code: str,
        df: pd.DataFrame,
        analysis_date_from: Optional[date],
        analysis_date_to: Optional[date],
        eval_window_days: int,
        only_passed: bool,
    ) -> List[ProfileBacktestItem]:
        items: List[ProfileBacktestItem] = []
        metadata = get_profile_stock_metadata(self.profile_service.profile.name, code)
        stock_name = metadata.name_zh if metadata else code

        last_entry_index = len(df) - eval_window_days - 1
        for idx in range(self.warmup_bars, last_entry_index + 1):
            signal_date = df.iloc[idx]["date"].date()
            if analysis_date_from and signal_date < analysis_date_from:
                continue
            if analysis_date_to and signal_date > analysis_date_to:
                continue

            signal_df = df.iloc[: idx + 1].copy()
            trend = self.profile_service.trend_analyzer.analyze(signal_df, code)
            signal = self.profile_service.signal_engine.evaluate(
                self.profile_service.strategy.name,
                signal_df,
                trend,
                self.profile_service.strategy.parameters,
            )
            if only_passed and not signal.passed:
                continue

            forward_df = df.iloc[idx + 1 : idx + 1 + eval_window_days].copy()
            if len(forward_df) < eval_window_days:
                continue

            entry_row = forward_df.iloc[0]
            exit_row = forward_df.iloc[-1]
            entry_price = float(entry_row["open"] if pd.notna(entry_row["open"]) else entry_row["close"])
            exit_price = float(exit_row["close"])
            max_high = float(forward_df["high"].max())
            min_low = float(forward_df["low"].min())
            window_return_pct = round((exit_price - entry_price) / entry_price * 100, 2)
            max_return_pct = round((max_high - entry_price) / entry_price * 100, 2)
            min_return_pct = round((min_low - entry_price) / entry_price * 100, 2)

            items.append(
                ProfileBacktestItem(
                    code=code,
                    stock_name=stock_name,
                    analysis_date=signal_date,
                    entry_date=entry_row["date"].date(),
                    exit_date=exit_row["date"].date(),
                    score=signal.score,
                    grade=signal.grade,
                    verdict=signal.verdict,
                    entry_price=round(entry_price, 4),
                    exit_price=round(exit_price, 4),
                    max_return_pct=max_return_pct,
                    min_return_pct=min_return_pct,
                    window_return_pct=window_return_pct,
                    outcome=self._resolve_outcome(window_return_pct),
                )
            )

        return items

    def _resolve_outcome(self, window_return_pct: float) -> str:
        if window_return_pct > self.neutral_band_pct:
            return "win"
        if window_return_pct < -self.neutral_band_pct:
            return "loss"
        return "neutral"

    def _build_summary(self, items: List[ProfileBacktestItem], eval_window_days: int) -> Dict[str, object]:
        total = len(items)
        wins = sum(1 for item in items if item.outcome == "win")
        losses = sum(1 for item in items if item.outcome == "loss")
        neutrals = sum(1 for item in items if item.outcome == "neutral")

        avg_return = round(sum(item.window_return_pct for item in items) / total, 2) if total else None
        avg_max_return = round(sum(item.max_return_pct for item in items) / total, 2) if total else None
        avg_min_return = round(sum(item.min_return_pct for item in items) / total, 2) if total else None
        win_rate = round(wins / total * 100, 2) if total else None

        by_code: Dict[str, Dict[str, object]] = {}
        grouped: Dict[str, List[ProfileBacktestItem]] = {}
        for item in items:
            grouped.setdefault(item.code, []).append(item)
        for code, rows in grouped.items():
            count = len(rows)
            code_wins = sum(1 for row in rows if row.outcome == "win")
            code_avg = round(sum(row.window_return_pct for row in rows) / count, 2) if count else None
            by_code[code] = {
                "stock_name": rows[0].stock_name,
                "signals": count,
                "win_rate_pct": round(code_wins / count * 100, 2) if count else None,
                "avg_return_pct": code_avg,
            }

        return {
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "neutrals": neutrals,
            "win_rate_pct": win_rate,
            "avg_return_pct": avg_return,
            "avg_max_return_pct": avg_max_return,
            "avg_min_return_pct": avg_min_return,
            "eval_window_days": eval_window_days,
            "by_code": by_code,
        }
