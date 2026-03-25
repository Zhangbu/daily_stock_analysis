# -*- coding: utf-8 -*-
"""
===================================
Data Cache Manager
===================================

Intelligent caching system with features:
1. Parquet format storage (3-5x faster than CSV)
2. Incremental updates (only fetch new data)
3. Automatic deduplication and sorting
4. Cache expiration detection
5. Cache invalidation support

This module provides a high-performance caching layer for stock data,
significantly reducing API calls and improving data retrieval speed.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Intelligent cache manager for stock data storage and retrieval.
    
    Features:
    - Uses Parquet format for efficient storage (compression + fast I/O)
    - Supports incremental updates by detecting last cached date
    - Automatic merging of old and new data
    - Cache invalidation based on market hours
    """
    
    def __init__(
        self,
        cache_dir: str = "data_cache",
        cache_format: str = "parquet",
        ttl_seconds: Optional[int] = None,
    ):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory to store cache files (default: "data_cache")
            cache_format: Storage format, "parquet" or "csv" (default: "parquet")
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_format = cache_format
        self.ttl_seconds = ttl_seconds
        self._stats: Dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "stale": 0,
            "writes": 0,
            "clears": 0,
            "read_errors": 0,
        }
        
        logger.debug(f"CacheManager initialized: dir={cache_dir}, format={cache_format}, ttl={ttl_seconds}")
    
    def get_cached_data(
        self,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve cached data with intelligent incremental update detection.
        
        This method checks if cached data exists and whether it's fresh enough
        to satisfy the request. If the cache contains data up to the expected
        latest date and covers the requested date range, it returns the cached
        data directly.
        
        Args:
            stock_code: Stock code (e.g., "600519", "000001")
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            
        Returns:
            DataFrame if cache is valid and covers requested range, None otherwise
        """
        cache_file = self.cache_dir / f"{stock_code}.{self.cache_format}"
        
        # No cache file exists
        if not cache_file.exists():
            self._stats["misses"] += 1
            logger.debug(f"Cache miss (file not found): {stock_code}")
            self._bump_global("misses")
            return None

        if self._is_cache_file_expired(cache_file):
            self._stats["stale"] += 1
            self._bump_global("stale")
            logger.info(f"Cache expired by TTL: {stock_code}")
            return None
        
        try:
            # Load cached data
            if self.cache_format == "parquet":
                df = pd.read_parquet(cache_file)
            else:
                df = pd.read_csv(cache_file)
            
            # Ensure date column is datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            else:
                logger.warning(f"Cache file missing 'date' column: {stock_code}")
                self._stats["read_errors"] += 1
                self._bump_global("read_errors")
                return None
            
            # Sort by date
            df = df.sort_values('date').reset_index(drop=True)
            
            # Check if cache needs update
            last_cached_date = df['date'].max().date()
            expected_latest = self._get_expected_latest_date()
            
            # Check date range coverage
            requested_start = pd.to_datetime(start_date).date()
            requested_end = pd.to_datetime(end_date).date()
            
            cache_start = df['date'].min().date()
            
            # Cache is valid if:
            # 1. Last cached date >= expected latest date (market closed or updated)
            # 2. Cache covers the requested start date
            if (last_cached_date >= expected_latest and 
                cache_start <= requested_start):
                
                # Filter to requested range
                df_filtered = df[
                    (df['date'] >= pd.to_datetime(start_date)) &
                    (df['date'] <= pd.to_datetime(end_date))
                ].copy()
                
                logger.debug(
                    f"Cache hit: {stock_code}, "
                    f"cached: {cache_start} ~ {last_cached_date}, "
                    f"requested: {requested_start} ~ {requested_end}, "
                    f"rows: {len(df_filtered)}"
                )
                self._stats["hits"] += 1
                self._bump_global("hits")
                return df_filtered
            
            # Cache is stale
            logger.info(
                f"Cache stale: {stock_code}, "
                f"last cached: {last_cached_date}, "
                f"expected: {expected_latest}"
            )
            self._stats["stale"] += 1
            self._bump_global("stale")
            return None
            
        except Exception as e:
            self._stats["read_errors"] += 1
            self._bump_global("read_errors")
            logger.warning(f"Failed to read cache for {stock_code}: {e}")
            return None
    
    def save_data(self, stock_code: str, data: pd.DataFrame) -> None:
        """
        Save data to cache with intelligent merging.
        
        If cached data already exists, this method merges the new data with
        the cached data, removes duplicates, and sorts by date. This enables
        incremental updates where only new data is fetched from the API.
        
        Args:
            stock_code: Stock code
            data: DataFrame to save (must contain 'date' column)
        """
        if data.empty:
            logger.warning(f"Attempted to save empty data for {stock_code}")
            return
        
        cache_file = self.cache_dir / f"{stock_code}.{self.cache_format}"
        
        try:
            # Ensure date column is datetime
            data = data.copy()
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date'])
            else:
                logger.error(f"Data missing 'date' column for {stock_code}")
                return
            
            # Merge with existing cache if it exists
            if cache_file.exists():
                old_data = pd.read_parquet(cache_file)
                old_data['date'] = pd.to_datetime(old_data['date'])
                
                # Concatenate and deduplicate
                combined = pd.concat([old_data, data], ignore_index=True)
                combined = combined.drop_duplicates(subset=['date'])
                combined = combined.sort_values('date').reset_index(drop=True)
                
                logger.debug(
                    f"Merged cache for {stock_code}: "
                    f"old={len(old_data)}, new={len(data)}, "
                    f"combined={len(combined)}"
                )
                data = combined
            
            # Save to cache
            if self.cache_format == "parquet":
                data.to_parquet(cache_file, index=False)
            else:
                data.to_csv(cache_file, index=False)
            
            self._stats["writes"] += 1
            self._bump_global("writes")
            logger.info(f"Cache saved: {stock_code}, rows: {len(data)}, file: {cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to save cache for {stock_code}: {e}")
    
    def _get_expected_latest_date(self) -> datetime.date:
        """
        Determine the expected latest data date based on current time.
        
        If current time is >= 15:00 (market close), expect today's data.
        Otherwise, expect yesterday's data.
        
        Returns:
            Expected latest date
        """
        now = datetime.now()
        
        # Market closes at 15:00
        if now.hour >= 15:
            return now.date()
        else:
            return (now - timedelta(days=1)).date()
    
    def clear_cache(self, stock_code: Optional[str] = None) -> None:
        """
        Clear cache for a specific stock or all stocks.
        
        Args:
            stock_code: Stock code to clear (None to clear all cache)
        """
        if stock_code:
            # Clear specific stock cache
            cache_file = self.cache_dir / f"{stock_code}.{self.cache_format}"
            if cache_file.exists():
                cache_file.unlink()
                self._stats["clears"] += 1
                self._bump_global("clears")
                logger.info(f"Cache cleared: {stock_code}")
            else:
                logger.debug(f"Cache file not found: {stock_code}")
        else:
            # Clear all cache
            count = 0
            for cache_file in self.cache_dir.glob(f"*.{self.cache_format}"):
                cache_file.unlink()
                count += 1
            
            self._stats["clears"] += count
            self._bump_global("clears", count)
            logger.info(f"Cleared all cache: {count} files")
    
    def get_cache_info(self, stock_code: Optional[str] = None) -> dict:
        """
        Get cache information for a specific stock or all stocks.
        
        Args:
            stock_code: Stock code (None to get all cache info)
            
        Returns:
            Dictionary with cache information
        """
        if stock_code:
            cache_file = self.cache_dir / f"{stock_code}.{self.cache_format}"
            if not cache_file.exists():
                return {'exists': False}
            
            stat = cache_file.stat()
            return {
                'exists': True,
                'file': str(cache_file),
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'last_modified': datetime.fromtimestamp(stat.st_mtime),
                'ttl_seconds': self.ttl_seconds,
            }
        else:
            # Get all cache info
            cache_files = list(self.cache_dir.glob(f"*.{self.cache_format}"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                'total_files': len(cache_files),
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'cache_dir': str(self.cache_dir),
                'ttl_seconds': self.ttl_seconds,
                'stats': self.get_cache_stats(),
            }

    def get_cache_stats(self) -> Dict[str, int]:
        """Return in-memory cache operation counters."""
        return dict(self._stats)

    @classmethod
    def get_global_cache_stats(cls) -> Dict[str, int]:
        """Return aggregate cache counters across all CacheManager instances."""
        return dict(cls._global_stats)

    @classmethod
    def reset_global_cache_stats(cls) -> None:
        """Reset aggregate cache counters for tests."""
        for key in cls._global_stats:
            cls._global_stats[key] = 0

    def _is_cache_file_expired(self, cache_file: Path) -> bool:
        """Check whether the file age exceeds the configured TTL."""
        if not self.ttl_seconds or self.ttl_seconds <= 0:
            return False
        age_seconds = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).total_seconds()
        return age_seconds > self.ttl_seconds

    @classmethod
    def _bump_global(cls, key: str, amount: int = 1) -> None:
        cls._global_stats[key] = cls._global_stats.get(key, 0) + amount
    _global_stats: Dict[str, int] = {
        "hits": 0,
        "misses": 0,
        "stale": 0,
        "writes": 0,
        "clears": 0,
        "read_errors": 0,
    }
