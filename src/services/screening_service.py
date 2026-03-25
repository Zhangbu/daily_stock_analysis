# -*- coding: utf-8 -*-
"""Stock screening service."""

import logging
from typing import List, Optional, Dict, Any, Tuple

import pandas as pd

from data_provider.base import DataFetcherManager
from src.core.trading_calendar import get_market_for_stock
from src.repositories.stock_repo import StockRepository
from screening.filter import StockFilter

logger = logging.getLogger(__name__)


class ScreeningService:
    """Service for stock screening operations."""
    
    def __init__(self):
        """Initialize the screening service."""
        self.fetcher_manager = DataFetcherManager()
        self.stock_filter = StockFilter(self.fetcher_manager)
        self.stock_repo = StockRepository()
        logger.info("ScreeningService initialized")
    
    def screen_stocks(
        self,
        market: str = "cn",
        data_mode: str = "database",
        min_market_cap: float = 10_000_000_000,
        max_market_cap: Optional[float] = None,
        min_turnover: float = 200_000_000,
        min_turnover_rate: float = 1.0,
        max_turnover_rate: float = 25.0,
        min_price: float = 5.0,
        max_price: Optional[float] = None,
        min_change_pct: float = -3.0,
        max_change_pct: float = 10.0,
        exclude_st: bool = True,
        exclude_prefixes: Optional[List[str]] = None,
        include_dragon_tiger: bool = False,
        target_count: int = 30,
        sort_by: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Screen stocks based on multiple criteria.
        
        Args:
            min_market_cap: Minimum market cap
            max_market_cap: Maximum market cap
            min_turnover: Minimum turnover
            min_turnover_rate: Minimum turnover rate
            max_turnover_rate: Maximum turnover rate
            min_price: Minimum price
            max_price: Maximum price
            min_change_pct: Minimum change percentage
            max_change_pct: Maximum change percentage
            exclude_st: Exclude ST stocks
            exclude_prefixes: Exclude stock code prefixes
            include_dragon_tiger: Include dragon-tiger list
            target_count: Target number of stocks
            sort_by: Sort by fields
            
        Returns:
            Dictionary with filtered stocks and summary
        """
        try:
            logger.info("Starting stock screening")

            if data_mode == "realtime":
                filtered_df = self.stock_filter.filter_stocks(
                    min_market_cap=min_market_cap,
                    max_market_cap=max_market_cap,
                    min_turnover=min_turnover,
                    min_turnover_rate=min_turnover_rate,
                    max_turnover_rate=max_turnover_rate,
                    min_price=min_price,
                    max_price=max_price,
                    min_change_pct=min_change_pct,
                    max_change_pct=max_change_pct,
                    exclude_st=exclude_st,
                    exclude_prefixes=exclude_prefixes,
                    include_dragon_tiger=include_dragon_tiger,
                    target_count=target_count,
                    sort_by=sort_by
                )
            else:
                filtered_df = self._screen_from_database(
                    market=market,
                    min_turnover=min_turnover,
                    min_price=min_price,
                    max_price=max_price,
                    min_change_pct=min_change_pct,
                    max_change_pct=max_change_pct,
                    target_count=target_count,
                )
            
            if filtered_df.empty:
                logger.warning("No stocks matched the screening criteria")
                return self._empty_response(market=market, data_mode=data_mode)
            
            # Get summary
            if data_mode == "realtime":
                summary = self.stock_filter.get_stock_screening_summary(filtered_df)
            else:
                summary = self._build_summary(filtered_df, market=market, data_mode=data_mode)
            
            # Convert DataFrame to list of dictionaries
            stocks = self._convert_df_to_stocks(filtered_df)
            
            logger.info(f"Screening completed: {len(stocks)} stocks found")
            
            return {
                'stocks': stocks,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Stock screening failed: {e}", exc_info=True)
            raise
    
    def _convert_df_to_stocks(self, df) -> List[Dict[str, Any]]:
        """
        Convert DataFrame to list of stock dictionaries.
        
        Args:
            df: Filtered DataFrame
            
        Returns:
            List of stock dictionaries
        """
        stocks = []
        
        for _, row in df.iterrows():
            stock = {
                'code': str(row.get('code', '')),
                'name': str(row.get('name', '')),
                'price': float(row.get('price', 0.0)),
                'market_cap': float(row.get('market_cap', 0.0)),
                'turnover': float(row.get('turnover', 0.0)),
                'turnover_rate': float(row.get('turnover_rate', 0.0)),
                'change_pct': float(row.get('change_pct', 0.0)),
                'rank': int(row.get('rank')) if pd.notna(row.get('rank')) else None,
                'score': float(row.get('score')) if pd.notna(row.get('score')) else None,
                'score_reason': str(row.get('score_reason', '')) if row.get('score_reason') else None,
                'score_breakdown': dict(row.get('score_breakdown') or {}),
                'opportunity_tier': str(row.get('opportunity_tier', '')) if row.get('opportunity_tier') else None,
            }
            
            # Add optional fields if available
            if 'open' in row and pd.notna(row['open']):
                stock['open'] = float(row['open'])
            if 'high' in row and pd.notna(row['high']):
                stock['high'] = float(row['high'])
            if 'low' in row and pd.notna(row['low']):
                stock['low'] = float(row['low'])
            if 'volume' in row and pd.notna(row['volume']):
                stock['volume'] = float(row['volume'])
            if 'amount' in row and pd.notna(row['amount']):
                stock['amount'] = float(row['amount'])
            
            stocks.append(stock)
        
        return stocks
    
    def _empty_response(self, *, market: str, data_mode: str) -> Dict[str, Any]:
        """
        Get empty response when no stocks found.
        
        Returns:
            Empty response dictionary
        """
        return {
            'stocks': [],
            'summary': {
                'count': 0,
                'avg_market_cap': 0.0,
                'avg_turnover': 0.0,
                'avg_turnover_rate': 0.0,
                'avg_price': 0.0,
                'avg_change_pct': 0.0,
                'market': market,
                'data_mode': data_mode,
                'top_score': 0.0,
                'avg_score': 0.0,
                'top_candidates': [],
            }
        }

    def _screen_from_database(
        self,
        *,
        market: str,
        min_turnover: float,
        min_price: float,
        max_price: Optional[float],
        min_change_pct: float,
        max_change_pct: float,
        target_count: int,
    ) -> pd.DataFrame:
        """Rank stocks from synced daily data instead of live whole-market spot data."""
        snapshots = self.stock_repo.get_latest_snapshots()
        rows: List[Dict[str, Any]] = []
        for snapshot in snapshots:
            code = str(snapshot.code).upper()
            if get_market_for_stock(code) != market:
                continue

            latest_close = float(snapshot.close or 0.0)
            if latest_close <= 0 or latest_close < min_price:
                continue
            if max_price is not None and latest_close > max_price:
                continue

            turnover = float(snapshot.amount or 0.0)
            if turnover < min_turnover:
                continue

            change_pct = float(snapshot.pct_chg or 0.0)
            if change_pct < min_change_pct or change_pct > max_change_pct:
                continue

            history = self.stock_repo.get_latest(code, days=60)
            score, reason, breakdown = self._score_stock_from_history(history)
            if score <= 0:
                continue

            rows.append(
                {
                    "code": code,
                    "name": code,
                    "price": latest_close,
                    "market_cap": 0.0,
                    "turnover": turnover,
                    "turnover_rate": 0.0,
                    "change_pct": change_pct,
                    "volume": float(snapshot.volume or 0.0),
                    "amount": turnover,
                    "score": score,
                    "score_reason": reason,
                    "score_breakdown": breakdown,
                    "opportunity_tier": self._score_to_tier(score),
                }
            )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = df.sort_values(["score", "turnover", "change_pct"], ascending=[False, False, False]).head(target_count)
        df = df.reset_index(drop=True)
        df["rank"] = range(1, len(df) + 1)
        return df

    def _score_stock_from_history(self, history: List[Any]) -> Tuple[float, str, Dict[str, float]]:
        """Score one stock using synced daily history."""
        if len(history) < 20:
            return 0.0, "insufficient_history", {}

        ordered = sorted(history, key=lambda item: item.date)
        closes = [float(item.close or 0.0) for item in ordered if item.close is not None]
        volumes = [float(item.volume or 0.0) for item in ordered if item.volume is not None]
        if len(closes) < 20:
            return 0.0, "insufficient_history", {}

        latest = ordered[-1]
        current = closes[-1]
        prev_5 = closes[-6] if len(closes) >= 6 else closes[0]
        prev_20 = closes[-21] if len(closes) >= 21 else closes[0]
        ma5 = latest.ma5 or (sum(closes[-5:]) / min(len(closes), 5))
        ma10 = latest.ma10 or (sum(closes[-10:]) / min(len(closes), 10))
        ma20 = latest.ma20 or (sum(closes[-20:]) / min(len(closes), 20))
        recent_high20 = max(closes[-20:])
        avg_volume20 = (sum(volumes[-20:]) / len(volumes[-20:])) if volumes[-20:] else 0.0
        latest_volume = float(latest.volume or 0.0)

        score = 0.0
        breakdown: Dict[str, float] = {
            "trend": 0.0,
            "momentum": 0.0,
            "pullback": 0.0,
            "volume": 0.0,
            "risk": 0.0,
            "consistency": 0.0,
        }
        reasons: List[str] = []
        returns = [
            (closes[idx] - closes[idx - 1]) / closes[idx - 1]
            for idx in range(1, len(closes))
            if closes[idx - 1] > 0
        ]

        if current > ma5 > ma10 > ma20:
            score += 35
            breakdown["trend"] += 35
            reasons.append("ma_bull")
        elif current > ma10 > ma20:
            score += 20
            breakdown["trend"] += 20
            reasons.append("trend_up")

        if prev_20 > 0:
            momentum_20 = (current - prev_20) / prev_20
            if momentum_20 > 0.08:
                score += 20
                breakdown["momentum"] += 20
                reasons.append("mom20")
            elif momentum_20 > 0.03:
                score += 10
                breakdown["momentum"] += 10
                reasons.append("mom20_soft")

        if prev_5 > 0:
            momentum_5 = (current - prev_5) / prev_5
            if momentum_5 > 0:
                score += 8
                breakdown["momentum"] += 8
                reasons.append("mom5")

        if recent_high20 > 0:
            pullback = (recent_high20 - current) / recent_high20
            if 0.02 <= pullback <= 0.08:
                score += 15
                breakdown["pullback"] += 15
                reasons.append("healthy_pullback")
            elif pullback > 0.15:
                score -= 8
                breakdown["pullback"] -= 8
                reasons.append("deep_pullback")

        if avg_volume20 > 0 and latest_volume > avg_volume20 * 1.5:
            score += 12
            breakdown["volume"] += 12
            reasons.append("volume_expand")

        recent_returns20 = returns[-20:] if len(returns) >= 20 else returns
        recent_returns60 = returns[-60:] if len(returns) >= 60 else returns
        if recent_returns20:
            daily_volatility = (sum((value ** 2 for value in recent_returns20)) / len(recent_returns20)) ** 0.5
            if daily_volatility <= 0.025:
                score += 12
                breakdown["risk"] += 12
                reasons.append("low_volatility")
            elif daily_volatility >= 0.06:
                score -= 10
                breakdown["risk"] -= 10
                reasons.append("high_volatility")

        if closes:
            peak = closes[0]
            max_drawdown = 0.0
            for close in closes:
                peak = max(peak, close)
                if peak > 0:
                    max_drawdown = max(max_drawdown, (peak - close) / peak)
            if max_drawdown <= 0.12:
                score += 10
                breakdown["risk"] += 10
                reasons.append("controlled_drawdown")
            elif max_drawdown >= 0.25:
                score -= 12
                breakdown["risk"] -= 12
                reasons.append("large_drawdown")

        if recent_returns60:
            positive_ratio = sum(1 for value in recent_returns60 if value > 0) / len(recent_returns60)
            if positive_ratio >= 0.58:
                score += 12
                breakdown["consistency"] += 12
                reasons.append("win_rate_proxy")
            elif positive_ratio >= 0.52:
                score += 6
                breakdown["consistency"] += 6
                reasons.append("win_rate_proxy_soft")

        return max(score, 0.0), ",".join(reasons), breakdown

    @staticmethod
    def _score_to_tier(score: float) -> str:
        if score >= 85:
            return "S"
        if score >= 65:
            return "A"
        if score >= 45:
            return "B"
        return "C"

    @staticmethod
    def _build_summary(df: pd.DataFrame, *, market: str, data_mode: str) -> Dict[str, Any]:
        return {
            "count": int(len(df)),
            "avg_market_cap": float(df["market_cap"].mean()) if "market_cap" in df else 0.0,
            "avg_turnover": float(df["turnover"].mean()) if "turnover" in df else 0.0,
            "avg_turnover_rate": float(df["turnover_rate"].mean()) if "turnover_rate" in df else 0.0,
            "avg_price": float(df["price"].mean()) if "price" in df else 0.0,
            "avg_change_pct": float(df["change_pct"].mean()) if "change_pct" in df else 0.0,
            "market": market,
            "data_mode": data_mode,
            "top_score": float(df["score"].max()) if "score" in df else 0.0,
            "avg_score": float(df["score"].mean()) if "score" in df else 0.0,
            "top_candidates": [str(code) for code in df["code"].head(5).tolist()] if "code" in df else [],
        }
