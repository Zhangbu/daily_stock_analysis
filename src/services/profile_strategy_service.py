# -*- coding: utf-8 -*-
"""
Profile-based strategy execution service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from data_provider.yfinance_fetcher import YfinanceFetcher
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult
from src.strategies import (
    ProfileDefinition,
    StrategyDefinition,
    StrategySignal,
    StrategySignalEngine,
    load_profile_definition,
    load_strategy_definition,
)


logger = logging.getLogger(__name__)

SUPPORTED_MAG7_STRATEGIES = [
    "mag7_ma_pullback",
    "mag7_breakout",
    "mag7_ma_cross",
]

SUPPORTED_PROFILE_STRATEGIES = {
    "mag7": SUPPORTED_MAG7_STRATEGIES,
    "nasdaq100": SUPPORTED_MAG7_STRATEGIES,
}


@dataclass
class ProfileStrategyResult:
    code: str
    profile_name: str
    strategy_name: str
    trend: TrendAnalysisResult
    signal: StrategySignal


class ProfileStrategyService:
    """Run a constrained strategy workflow for a selected profile."""

    def __init__(self, profile_name: str, strategy_name: Optional[str] = None):
        self.profile: ProfileDefinition = load_profile_definition(profile_name)
        resolved_strategy_name = strategy_name or self.profile.default_strategy
        if not resolved_strategy_name:
            raise ValueError(f"Profile {profile_name} has no default strategy.")
        self.strategy: StrategyDefinition = load_strategy_definition(resolved_strategy_name)

        if self.profile.data_source != "yfinance":
            raise ValueError(f"Unsupported profile data source: {self.profile.data_source}")

        self.fetcher = YfinanceFetcher()
        self.trend_analyzer = StockTrendAnalyzer()
        self.signal_engine = StrategySignalEngine()

    @staticmethod
    def get_available_strategy_names(profile_name: str) -> List[str]:
        strategies = SUPPORTED_PROFILE_STRATEGIES.get(profile_name)
        if strategies is not None:
            return list(strategies)
        raise ValueError(f"Unsupported profile: {profile_name}")

    def resolve_stock_codes(self, stocks_override: Optional[List[str]] = None) -> List[str]:
        if stocks_override:
            return [str(code).strip().upper() for code in stocks_override if str(code).strip()]
        return list(self.profile.stock_universe)

    def run(self, stocks_override: Optional[List[str]] = None) -> List[ProfileStrategyResult]:
        results: List[ProfileStrategyResult] = []
        stock_codes = self.resolve_stock_codes(stocks_override)

        for code in stock_codes:
            logger.info(
                "[ProfileStrategy] Running profile=%s strategy=%s code=%s",
                self.profile.name,
                self.strategy.name,
                code,
            )
            df = self.fetcher.get_daily_data(code, days=self.profile.lookback_days)
            trend = self.trend_analyzer.analyze(df, code)
            signal = self.signal_engine.evaluate(self.strategy.name, df, trend, self.strategy.parameters)
            results.append(
                ProfileStrategyResult(
                    code=code,
                    profile_name=self.profile.name,
                    strategy_name=self.strategy.name,
                    trend=trend,
                    signal=signal,
                )
            )

        return sorted(results, key=lambda item: item.signal.score, reverse=True)

    def format_report(self, results: List[ProfileStrategyResult]) -> str:
        lines = [
            f"=== {self.profile.display_name} | {self.strategy.display_name} ===",
            self.profile.description,
            f"Data Source: {self.profile.data_source}",
            "",
        ]

        for item in results:
            signal = item.signal
            trend = item.trend
            lines.extend(
                [
                    f"[{signal.grade}] {item.code} | {signal.verdict} | Score {signal.score}",
                    (
                        f"Price {signal.metrics['price']:.2f} | "
                        f"MA5 {signal.metrics['ma5']:.2f} | "
                        f"MA10 {signal.metrics['ma10']:.2f} | "
                        f"MA20 {signal.metrics['ma20']:.2f}"
                    ),
                    f"Trend: {trend.trend_status.value} | Buy Signal: {trend.buy_signal.value}",
                    f"Entry Zone: {signal.entry_zone}",
                    f"Stop Loss: {signal.stop_loss}",
                    f"Target Hint: {signal.target_hint}",
                    "Reasons:",
                ]
            )
            for reason in signal.reasons[:4]:
                lines.append(f"  - {reason}")

            if signal.risks:
                lines.append("Risks:")
                for risk in signal.risks[:3]:
                    lines.append(f"  - {risk}")
            lines.append("")

        return "\n".join(lines).rstrip()
