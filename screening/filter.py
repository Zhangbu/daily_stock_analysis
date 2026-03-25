# -*- coding: utf-8 -*-
"""
===================================
Multi-dimensional Stock Filter
===================================

Advanced stock screening with multiple filtering criteria.

Features:
1. Fundamental filters (market cap, turnover, turnover rate, price)
2. Technical filters (change percentage, MA alignment)
3. Dragon-tiger list integration
4. Comprehensive scoring and ranking
5. Configurable filtering criteria

Usage:
    manager = DataFetcherManager()
    filter = StockFilter(manager)
    
    filtered_stocks = filter.filter_stocks(
        min_market_cap=10_000_000_000,  # 10 billion
        min_turnover=200_000_000,        # 200 million
        target_count=30
    )
"""

import logging
from typing import List, Optional, Dict, Any
import pandas as pd

from data_provider.base import DataFetcherManager, normalize_stock_code

logger = logging.getLogger(__name__)


class StockFilter:
    """
    Multi-dimensional stock filtering system.
    
    This class provides comprehensive stock screening capabilities
    with multiple filtering criteria and intelligent ranking.
    """
    
    def __init__(self, fetcher_manager: DataFetcherManager):
        """
        Initialize the stock filter.
        
        Args:
            fetcher_manager: DataFetcherManager instance for data fetching
        """
        self.fetcher = fetcher_manager
        logger.info("StockFilter initialized")
    
    def filter_stocks(
        self,
        min_market_cap: float = 10_000_000_000,  # 10 billion
        max_market_cap: Optional[float] = None,
        min_turnover: float = 200_000_000,        # 200 million
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
        sort_by: List[str] = None
    ) -> pd.DataFrame:
        """
        Multi-dimensional stock filtering.
        
        Args:
            min_market_cap: Minimum market cap (default: 10 billion)
            max_market_cap: Maximum market cap (optional)
            min_turnover: Minimum turnover (default: 200 million)
            min_turnover_rate: Minimum turnover rate % (default: 1.0)
            max_turnover_rate: Maximum turnover rate % (default: 25.0)
            min_price: Minimum stock price (default: 5.0)
            max_price: Maximum stock price (optional)
            min_change_pct: Minimum change % (default: -3.0)
            max_change_pct: Maximum change % (default: 10.0)
            exclude_st: Exclude ST stocks (default: True)
            exclude_prefixes: Exclude stock codes with these prefixes
            include_dragon_tiger: Include dragon-tiger list stocks (default: False)
            target_count: Target number of stocks (default: 30)
            sort_by: Sort by these fields (default: ['turnover', 'turnover_rate'])
            
        Returns:
            Filtered DataFrame with stock information
        """
        if exclude_prefixes is None:
            exclude_prefixes = ['688', '300']  # Exclude STAR Market and ChiNext
        
        if sort_by is None:
            sort_by = ['turnover', 'turnover_rate', 'market_cap']
        
        # Get all stocks
        all_stocks = self._get_all_stocks()
        
        if all_stocks.empty:
            logger.warning("No stocks available for filtering")
            return pd.DataFrame()
        
        logger.info(f"Initial stock count: {len(all_stocks)}")
        
        # Apply filters
        filtered = all_stocks.copy()
        
        # 1. Exclude ST stocks
        if exclude_st:
            filtered = self._filter_st_stocks(filtered)
            logger.info(f"After ST filter: {len(filtered)}")
        
        # 2. Exclude specified prefixes
        if exclude_prefixes:
            filtered = self._filter_by_prefixes(filtered, exclude_prefixes)
            logger.info(f"After prefix filter: {len(filtered)}")
        
        # 3. Market cap filter
        filtered = self._filter_by_market_cap(filtered, min_market_cap, max_market_cap)
        logger.info(f"After market cap filter: {len(filtered)}")
        
        # 4. Turnover filter
        filtered = self._filter_by_turnover(filtered, min_turnover)
        logger.info(f"After turnover filter: {len(filtered)}")
        
        # 5. Turnover rate filter
        filtered = self._filter_by_turnover_rate(filtered, min_turnover_rate, max_turnover_rate)
        logger.info(f"After turnover rate filter: {len(filtered)}")
        
        # 6. Price filter
        filtered = self._filter_by_price(filtered, min_price, max_price)
        logger.info(f"After price filter: {len(filtered)}")
        
        # 7. Change percentage filter
        filtered = self._filter_by_change_pct(filtered, min_change_pct, max_change_pct)
        logger.info(f"After change pct filter: {len(filtered)}")
        
        # 8. Dragon-tiger list filter (optional)
        if include_dragon_tiger:
            filtered = self._filter_dragon_tiger(filtered)
            logger.info(f"After dragon-tiger filter: {len(filtered)}")
        
        # 9. Rank and limit to target count
        if len(filtered) > target_count:
            filtered = self._rank_and_limit(filtered, sort_by, target_count)
            logger.info(f"After ranking: {len(filtered)}")
        
        logger.info(f"Final filtered stocks: {len(filtered)}")
        return filtered
    
    def _get_all_stocks(self) -> pd.DataFrame:
        """Get all stocks from available data sources."""
        try:
            # Try akshare first for comprehensive stock list
            import akshare as ak
            
            # Get A-share stock list
            df = ak.stock_zh_a_spot_em()
            
            if df is not None and not df.empty:
                return self._standardize_columns(df)
            
        except ImportError:
            logger.debug("akshare not available")
        except Exception as e:
            logger.warning(f"Failed to get stock list from akshare: {e}")
        
        try:
            # Try efinance as fallback
            import efinance as ef
            
            df = ef.stock.get_base_info()
            
            if df is not None and not df.empty:
                return self._standardize_columns(df)
            
        except ImportError:
            logger.debug("efinance not available")
        except Exception as e:
            logger.warning(f"Failed to get stock list from efinance: {e}")
        
        logger.warning("Unable to get stock list from any source")
        return pd.DataFrame()
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names from different data sources."""
        # Common column mappings for different data sources
        column_mappings = [
            # akshare format
            {
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '总市值': 'market_cap',
                '成交额': 'turnover',
                '换手率': 'turnover_rate',
                '涨跌幅': 'change_pct'
            },
            # efinance format
            {
                '股票代码': 'code',
                '股票名称': 'name',
                '最新价': 'price',
                '总市值': 'market_cap',
                '成交额': 'turnover',
                '换手率': 'turnover_rate',
                '涨跌幅': 'change_pct'
            },
            # English format
            {
                'code': 'code',
                'name': 'name',
                'price': 'price',
                'market_cap': 'market_cap',
                'turnover': 'turnover',
                'turnover_rate': 'turnover_rate',
                'change_pct': 'change_pct'
            }
        ]
        
        # Try each mapping
        for mapping in column_mappings:
            try:
                # Check if all source columns exist
                if all(col in df.columns for col in mapping.keys()):
                    df = df.rename(columns=mapping)
                    
                    # Convert data types
                    numeric_cols = ['market_cap', 'turnover', 'turnover_rate', 'change_pct', 'price']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    return df
            except Exception:
                continue
        
        # If no mapping works, return as-is
        logger.warning("Unable to standardize column names")
        return df
    
    def _filter_st_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter out ST stocks."""
        if 'name' not in df.columns:
            return df
        
        return df[~df['name'].str.contains('ST', case=False, na=False, regex=True)]
    
    def _filter_by_prefixes(self, df: pd.DataFrame, prefixes: List[str]) -> pd.DataFrame:
        """Filter stocks by code prefixes."""
        if 'code' not in df.columns:
            return df
        
        mask = ~df['code'].str.startswith(tuple(prefixes))
        return df[mask]
    
    def _filter_by_market_cap(
        self,
        df: pd.DataFrame,
        min_cap: float,
        max_cap: Optional[float] = None
    ) -> pd.DataFrame:
        """Filter by market cap."""
        if 'market_cap' not in df.columns:
            return df
        
        mask = df['market_cap'] >= min_cap
        
        if max_cap is not None:
            mask &= df['market_cap'] <= max_cap
        
        return df[mask]
    
    def _filter_by_turnover(self, df: pd.DataFrame, min_turnover: float) -> pd.DataFrame:
        """Filter by turnover."""
        if 'turnover' not in df.columns:
            return df
        
        return df[df['turnover'] >= min_turnover]
    
    def _filter_by_turnover_rate(
        self,
        df: pd.DataFrame,
        min_rate: float,
        max_rate: float
    ) -> pd.DataFrame:
        """Filter by turnover rate."""
        if 'turnover_rate' not in df.columns:
            return df
        
        mask = (df['turnover_rate'] >= min_rate) & (df['turnover_rate'] <= max_rate)
        return df[mask]
    
    def _filter_by_price(
        self,
        df: pd.DataFrame,
        min_price: float,
        max_price: Optional[float] = None
    ) -> pd.DataFrame:
        """Filter by price."""
        if 'price' not in df.columns:
            return df
        
        mask = df['price'] >= min_price
        
        if max_price is not None:
            mask &= df['price'] <= max_price
        
        return df[mask]
    
    def _filter_by_change_pct(
        self,
        df: pd.DataFrame,
        min_pct: float,
        max_pct: float
    ) -> pd.DataFrame:
        """Filter by change percentage."""
        if 'change_pct' not in df.columns:
            return df
        
        mask = (df['change_pct'] >= min_pct) & (df['change_pct'] <= max_pct)
        return df[mask]
    
    def _filter_dragon_tiger(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter to only include dragon-tiger list stocks."""
        dragon_tiger_codes = self._get_dragon_tiger_list()
        
        if not dragon_tiger_codes:
            logger.debug("No dragon-tiger list data available")
            return df
        
        intersection = set(df['code']) & dragon_tiger_codes
        
        if not intersection:
            logger.info("No stocks in dragon-tiger list after filtering")
            return pd.DataFrame()
        
        logger.info(f"Dragon-tiger intersection: {len(intersection)} stocks")
        return df[df['code'].isin(intersection)]
    
    def _get_dragon_tiger_list(self) -> set:
        """Get dragon-tiger list stock codes."""
        try:
            import akshare as ak
            
            # Get recent dragon-tiger list
            df = ak.stock_lhb_stock_statistic_em(symbol="近三月")
            
            if df is not None and not df.empty and '买方机构次数' in df.columns:
                df['买方机构次数'] = pd.to_numeric(df['买方机构次数'], errors='coerce').fillna(0)
                
                # Filter stocks with multiple institutional buys
                mask = df['买方机构次数'] > 1
                codes = df.loc[mask, '代码'].astype(str).tolist()
                
                logger.info(f"Dragon-tiger list: {len(codes)} stocks")
                return set(codes)
            
        except ImportError:
            logger.debug("akshare not available for dragon-tiger list")
        except Exception as e:
            logger.warning(f"Failed to get dragon-tiger list: {e}")
        
        return set()
    
    def _rank_and_limit(self, df: pd.DataFrame, sort_by: List[str], target_count: int) -> pd.DataFrame:
        """Rank stocks and limit to target count."""
        # Build sorting key
        ascending = []
        for field in sort_by:
            if field in ['turnover', 'turnover_rate']:
                ascending.append(False)  # Higher is better
            elif field == 'market_cap':
                ascending.append(True)   # Lower is better (prefer mid-cap)
            else:
                ascending.append(False)
        
        # Sort by multiple criteria
        df_sorted = df.sort_values(by=sort_by, ascending=ascending)
        
        # Limit to target count
        return df_sorted.head(target_count)
    
    def get_stock_screening_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get summary statistics of filtered stocks."""
        if df.empty:
            return {'count': 0}
        
        summary = {
            'count': len(df),
            'avg_market_cap': df['market_cap'].mean() if 'market_cap' in df.columns else 0,
            'avg_turnover': df['turnover'].mean() if 'turnover' in df.columns else 0,
            'avg_turnover_rate': df['turnover_rate'].mean() if 'turnover_rate' in df.columns else 0,
            'avg_price': df['price'].mean() if 'price' in df.columns else 0,
            'avg_change_pct': df['change_pct'].mean() if 'change_pct' in df.columns else 0,
        }
        
        return summary
    
    def export_filtered_stocks(self, df: pd.DataFrame, filename: str = "filtered_stocks.csv") -> None:
        """Export filtered stocks to CSV file."""
        if df.empty:
            logger.warning("No stocks to export")
            return
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"Exported {len(df)} stocks to {filename}")