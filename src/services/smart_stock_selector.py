# -*- coding: utf-8 -*-
"""Smart stock selector service - select stocks from synced market data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd

from src.config import Config, get_config
from src.repositories.stock_repo import StockRepository
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class StockScore:
    """Stock with selection score."""
    code: str
    name: str
    score: float
    reason: str
    today_close: float
    today_change_pct: float
    volume_ratio: float


class SmartStockSelector:
    """Select stocks from synced market data based on configurable strategies."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        config: Optional[Config] = None,
    ) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.config = config or get_config()
        self.stock_repo = StockRepository(self.db)

    def select(
        self,
        strategy: str = "best_performer",
        count: int = 10,
        exclude_codes: Optional[List[str]] = None,
    ) -> List[StockScore]:
        """
        Select top stocks from synced data based on strategy.

        Args:
            strategy: Selection strategy
                - best_performer: Best performers today
                - volume_surge: Highest volume ratio
                - ma_golden_cross: MA5 crossed above MA10
                - bottom_volume: Bottom volume (low volume after decline)
                - all_strategies: Combined scoring
            count: Number of stocks to select
            exclude_codes: Stock codes to exclude

        Returns:
            List of StockScore objects sorted by score descending
        """
        exclude_codes = exclude_codes or []

        if strategy == "all_strategies":
            return self._select_combined(count, exclude_codes)
        elif strategy == "ma_golden_cross":
            return self._select_ma_golden_cross(count, exclude_codes)
        elif strategy == "bottom_volume":
            return self._select_bottom_volume(count, exclude_codes)
        elif strategy == "volume_surge":
            return self._select_volume_surge(count, exclude_codes)
        else:  # best_performer (default)
            return self._select_best_performer(count, exclude_codes)

    def _get_today_data(self) -> pd.DataFrame:
        """Get today's market data for all synced stocks."""
        today = date.today()
        yesterday = today - timedelta(days=3)  # Buffer for weekend

        # Get all stocks with today's data
        all_data = []
        for record in self.stock_repo.get_range_for_all(today, yesterday):
            all_data.append({
                'code': record.code,
                'date': record.date,
                'close': record.close,
                'open': record.open,
                'high': record.high,
                'low': record.low,
                'volume': record.volume,
                'amount': record.amount,
                'pct_chg': record.pct_chg,
                'volume_ratio': record.volume_ratio,
                'ma5': record.ma5,
                'ma10': record.ma10,
                'ma20': record.ma20,
            })

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        return df

    def _select_best_performer(
        self,
        count: int,
        exclude_codes: List[str]
    ) -> List[StockScore]:
        """Select stocks with highest gains today."""
        df = self._get_today_data()
        if df.empty:
            return []

        # Filter out excluded codes
        df = df[~df['code'].isin(exclude_codes)]

        # Sort by pct_chg descending
        df = df.sort_values('pct_chg', ascending=False)

        results = []
        for _, row in df.head(count).iterrows():
            results.append(StockScore(
                code=row['code'],
                name="",  # Name not available in this context
                score=row['pct_chg'],
                reason=f"今日涨幅 {row['pct_chg']:.2f}%",
                today_close=row['close'],
                today_change_pct=row['pct_chg'],
                volume_ratio=row.get('volume_ratio', 0) or 0,
            ))

        return results

    def _select_volume_surge(
        self,
        count: int,
        exclude_codes: List[str]
    ) -> List[StockScore]:
        """Select stocks with highest volume ratio."""
        df = self._get_today_data()
        if df.empty:
            return []

        # Filter out excluded codes and invalid volume_ratio
        df = df[~df['code'].isin(exclude_codes)]
        df = df[df['volume_ratio'] > 0]

        # Sort by volume_ratio descending
        df = df.sort_values('volume_ratio', ascending=False)

        results = []
        for _, row in df.head(count).iterrows():
            results.append(StockScore(
                code=row['code'],
                name="",
                score=row['volume_ratio'],
                reason=f"量比 {row['volume_ratio']:.2f}",
                today_close=row['close'],
                today_change_pct=row['pct_chg'],
                volume_ratio=row['volume_ratio'],
            ))

        return results

    def _select_ma_golden_cross(
        self,
        count: int,
        exclude_codes: List[str]
    ) -> List[StockScore]:
        """Select stocks where MA5 crossed above MA10."""
        df = self._get_today_data()
        if df.empty:
            return []

        # Filter out excluded codes
        df = df[~df['code'].isin(exclude_codes)]

        # Need MA5 > MA10 and both valid
        df = df[(df['ma5'] > 0) & (df['ma10'] > 0) & (df['ma5'] > df['ma10'])]

        # Score by how strong the golden cross is (MA5/MA10 ratio)
        df['golden_score'] = (df['ma5'] - df['ma10']) / df['ma10'] * 100

        # Also consider today's performance
        df = df.sort_values('golden_score', ascending=False)

        results = []
        for _, row in df.head(count).iterrows():
            results.append(StockScore(
                code=row['code'],
                name="",
                score=row['golden_score'],
                reason=f"均线金叉 (MA5>{row['ma5']:.2f} > MA10>{row['ma10']:.2f})",
                today_close=row['close'],
                today_change_pct=row['pct_chg'],
                volume_ratio=row.get('volume_ratio', 0) or 0,
            ))

        return results

    def _select_bottom_volume(
        self,
        count: int,
        exclude_codes: List[str]
    ) -> List[StockScore]:
        """
        Select stocks with bottom volume pattern.

        Pattern: Recent decline + today's volume significantly lower than average
        """
        df = self._get_today_data()
        if df.empty:
            return []

        # Filter out excluded codes
        df = df[~df['code'].isin(exclude_codes)]

        # Need historical data to compare volume
        # For simplicity, use volume_ratio < 0.5 as "low volume" signal
        df_low_vol = df[(df['volume_ratio'] > 0) & (df['volume_ratio'] < 0.5)]

        if df_low_vol.empty:
            return []

        # Score by how low the volume is (lower = higher score for this strategy)
        df_low_vol['bottom_score'] = 1 / df_low_vol['volume_ratio']

        # Also prefer stocks that declined recently (potential bottom)
        df_low_vol = df_low_vol.sort_values('bottom_score', ascending=False)

        results = []
        for _, row in df_low_vol.head(count).iterrows():
            results.append(StockScore(
                code=row['code'],
                name="",
                score=row['bottom_score'],
                reason=f"底部缩量 (量比 {row['volume_ratio']:.2f})",
                today_close=row['close'],
                today_change_pct=row['pct_chg'],
                volume_ratio=row['volume_ratio'],
            ))

        return results

    def _select_combined(
        self,
        count: int,
        exclude_codes: List[str]
    ) -> List[StockScore]:
        """
        Combined scoring using multiple strategies.

        Scoring factors:
        - Today's performance (30%)
        - Volume ratio (25%)
        - MA alignment (25%)
        - Recent momentum (20%)
        """
        df = self._get_today_data()
        if df.empty:
            return []

        # Filter out excluded codes
        df = df[~df['code'].isin(exclude_codes)]

        # Calculate component scores (0-100 scale)

        # 1. Performance score (normalize pct_chg to 0-100)
        # Assume pct_chg range -10% to +10%
        df['score_perf'] = ((df['pct_chg'] + 10) / 20 * 100).clip(0, 100)

        # 2. Volume score (volume_ratio 0-5 maps to 0-100)
        df['score_vol'] = (df['volume_ratio'].fillna(1).clip(0, 5) / 5 * 100)

        # 3. MA alignment score
        # Bullish: close > MA5 > MA10 > MA20
        df['score_ma'] = 0
        bullish = (df['close'] > df['ma5']) & (df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20'])
        df.loc[bullish, 'score_ma'] = 100
        # Partial bullish
        partial = (df['close'] > df['ma5']) & (df['ma5'] > df['ma10'])
        df.loc[partial & ~bullish, 'score_ma'] = 60

        # 4. Momentum score (simplified: use today's pct_chg as proxy)
        df['score_mom'] = df['score_perf']

        # Combined score
        df['total_score'] = (
            df['score_perf'] * 0.30 +
            df['score_vol'] * 0.25 +
            df['score_ma'] * 0.25 +
            df['score_mom'] * 0.20
        )

        # Sort by total score
        df = df.sort_values('total_score', ascending=False)

        results = []
        for _, row in df.head(count).iterrows():
            results.append(StockScore(
                code=row['code'],
                name="",
                score=row['total_score'],
                reason=f"综合评分 (绩效{row['score_perf']:.0f} + 量能{row['score_vol']:.0f} + 均线{row['score_ma']:.0f})",
                today_close=row['close'],
                today_change_pct=row['pct_chg'],
                volume_ratio=row.get('volume_ratio', 0) or 0,
            ))

        return results


def select_from_synced_data(
    strategy: str = "best_performer",
    count: int = 10,
    exclude_codes: Optional[List[str]] = None,
    config: Optional[Config] = None,
) -> List[str]:
    """
    Convenience function to select stock codes from synced data.

    Args:
        strategy: Selection strategy
        count: Number of stocks to select
        exclude_codes: Stock codes to exclude
        config: Config object (optional)

    Returns:
        List of selected stock codes
    """
    config = config or get_config()
    selector = SmartStockSelector(config=config)

    results = selector.select(
        strategy=strategy,
        count=count,
        exclude_codes=exclude_codes or [],
    )

    selected_codes = [r.code for r in results]

    if selected_codes:
        logger.info(
            f"智能选股完成：策略={strategy}, 选中 {len(selected_codes)} 只股票，"
            f"代码：{', '.join(selected_codes)}"
        )

    return selected_codes
