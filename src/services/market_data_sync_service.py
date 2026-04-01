# -*- coding: utf-8 -*-
"""Background market data sync service for CN/US stock universes."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from src.config import Config, get_config
from src.core.trading_calendar import get_market_for_stock
from src.repositories.stock_repo import StockRepository
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

# 断点续传文件路径
SYNC_CHECKPOINT_FILE = Path(__file__).parent.parent.parent / "data" / "market_sync_checkpoint.json"


@dataclass
class MarketSyncStatus:
    """Mutable runtime status for one sync task."""

    running: bool = False
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    current_market: Optional[str] = None
    current_code: Optional[str] = None
    processed: int = 0
    saved: int = 0
    skipped: int = 0
    errors: int = 0
    total_candidates: int = 0
    priority_candidates: int = 0
    priority_processed: int = 0
    priority_completed: int = 0
    message: str = ""
    markets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_market": self.current_market,
            "current_code": self.current_code,
            "processed": self.processed,
            "saved": self.saved,
            "skipped": self.skipped,
            "errors": self.errors,
            "total_candidates": self.total_candidates,
            "priority_candidates": self.priority_candidates,
            "priority_processed": self.priority_processed,
            "priority_completed": self.priority_completed,
            "message": self.message,
            "markets": list(self.markets),
        }


class MarketDataSyncService:
    """Incrementally sync market-wide daily data with watchlist priority."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        config: Optional[Config] = None,
    ) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.config = config or get_config()
        self.stock_repo = StockRepository(self.db)
        self._lock = threading.Lock()
        self._status = MarketSyncStatus(message="idle")
        self._worker: Optional[threading.Thread] = None

    def get_status(self) -> Dict[str, Any]:
        """Return current sync status snapshot."""
        with self._lock:
            return self._status.to_dict()

    def _get_all_watchlist_codes(self) -> List[str]:
        """Return merged watchlist codes with backward compatibility for tests and legacy config."""
        if hasattr(self.config, "all_stock_list"):
            return list(self.config.all_stock_list)

        merged: List[str] = []
        seen = set()
        for code in [
            *getattr(self.config, "stock_list", []),
            *getattr(self.config, "hk_stock_list", []),
            *getattr(self.config, "us_stock_list", []),
        ]:
            normalized = str(code).strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged

    def start_background_sync(self, markets: Optional[Sequence[str]] = None) -> bool:
        """Start a background sync if no sync is currently running."""
        with self._lock:
            if self._status.running:
                return False

            selected_markets = self._normalize_markets(markets or self.config.market_sync_markets)
            self._status = MarketSyncStatus(
                running=True,
                started_at=datetime.now().isoformat(),
                message="sync started",
                markets=selected_markets,
            )

        worker = threading.Thread(
            target=self._run_sync,
            args=(selected_markets,),
            daemon=True,
            name="market-data-sync",
        )
        self._worker = worker
        worker.start()
        return True

    def _run_sync(self, markets: Sequence[str]) -> None:
        """Run the sync loop in a background thread."""
        try:
            priority_codes = {
                str(code).strip().upper()
                for code in self._get_all_watchlist_codes()
                if get_market_for_stock(code) in set(markets)
            }
            self._set_status(priority_candidates=len(priority_codes))

            for market in markets:
                self._set_status(current_market=market, message=f"syncing {market} market")
                codes, latest_dates_map = self._get_market_universe(market)
                self._set_status(total_candidates=self._status.total_candidates + len(codes))

                # 跟踪已同步的股票，用于断点续传
                synced_codes: List[str] = []

                for code in codes:
                    self._set_status(current_code=code)
                    is_priority = code in priority_codes
                    try:
                        # 传递已查询的最新日期，避免重复查询
                        latest_date = latest_dates_map.get(code)
                        saved = self._sync_single_code(code, cached_latest_date=latest_date)
                        if saved > 0:
                            self._increment_status(
                                processed=1,
                                saved=saved,
                                priority_processed=1 if is_priority else 0,
                                priority_completed=1 if is_priority else 0,
                            )
                        else:
                            self._increment_status(
                                processed=1,
                                skipped=1,
                                priority_processed=1 if is_priority else 0,
                                priority_completed=1 if is_priority else 0,
                            )

                        # 保存断点（无论是否实际保存数据，都记录进度）
                        synced_codes.append(code)
                        self._save_checkpoint(market, code, synced_codes)

                    except Exception as exc:
                        logger.warning("Market data sync failed for %s: %s", code, exc)
                        self._increment_status(
                            processed=1,
                            errors=1,
                            priority_processed=1 if is_priority else 0,
                        )

                    sleep_seconds = float(self.config.market_sync_sleep_seconds)
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)

                # 完成一个市场的同步后清除断点
                self._clear_checkpoint(market)
                logger.info(f"Market {market} sync completed: {len(synced_codes)} stocks processed")

            self._set_status(
                running=False,
                finished_at=datetime.now().isoformat(),
                current_code=None,
                current_market=None,
                message="sync finished",
            )
        except Exception as exc:
            logger.error("Market data sync crashed: %s", exc, exc_info=True)
            self._set_status(
                running=False,
                finished_at=datetime.now().isoformat(),
                current_code=None,
                message=f"sync failed: {exc}",
            )

    def _sync_single_code(self, code: str, cached_latest_date: Optional[date] = None) -> int:
        """Sync one stock code with incremental fallback when history already exists.

        Args:
            code: Stock code to sync
            cached_latest_date: Pre-fetched latest trade date (optional, to avoid duplicate DB queries)

        Returns:
            Number of rows saved
        """
        from data_provider.base import DataFetcherManager

        # 使用缓存的最新日期，如果没有则查询数据库
        if cached_latest_date is not None:
            latest_trade_date = cached_latest_date
        else:
            latest_trade_date = self.stock_repo.get_latest_trade_date(code)

        today = date.today()
        manager = DataFetcherManager()

        if latest_trade_date is None:
            days = int(self.config.market_sync_historical_days)
            df, source = manager.get_daily_data(code, days=days)
        else:
            if latest_trade_date >= today:
                return 0
            start_date = max(today - timedelta(days=int(self.config.market_sync_incremental_days) * 3), latest_trade_date - timedelta(days=2))
            df, source = manager.get_daily_data(
                code,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=today.strftime("%Y-%m-%d"),
                days=int(self.config.market_sync_incremental_days),
            )

        if df is None or df.empty:
            return 0
        return self.db.save_daily_data(df, code=code, data_source=source)

    def _get_market_universe(self, market: str) -> tuple[List[str], Dict[str, Optional[date]]]:
        """Resolve prioritized stock universe for one market.

        Returns:
            tuple: (codes list, latest_dates map)
        """
        if market == "cn":
            codes = self._get_cn_universe_filtered()  # 使用筛选后的股票池
        elif market == "hk":
            codes = self._get_hk_universe()
        elif market == "us":
            codes = self._get_us_universe()
        else:
            codes = []

        # 跳过已同步到最新的股票，同时返回最新日期映射
        codes, latest_dates_map = self._filter_fresh_codes_with_map(codes)

        # 断点续传：加载上次的进度
        if market in (self._status.current_market or ''):
            checkpoint = self._load_checkpoint(market)
            if checkpoint and checkpoint.get('last_code'):
                logger.info(f"断点续传：从 {checkpoint['last_code']} 继续，已同步 {checkpoint.get('synced_count', 0)} 只")
                # 已同步过的股票从列表中移除
                synced_codes = set(checkpoint.get('synced_codes', []))
                codes = [c for c in codes if c not in synced_codes]
                # 从映射中移除已同步的股票
                for synced in synced_codes:
                    latest_dates_map.pop(synced, None)
                logger.info(f"断点续传：跳过已同步的 {len(synced_codes)} 只股票，剩余 {len(codes)} 只待同步")

        max_codes = int(self.config.market_sync_max_codes_per_run)
        if max_codes > 0:
            codes = codes[:max_codes]
        return codes, latest_dates_map

    def _get_cn_universe(self) -> List[str]:
        """Build CN universe with watchlist-first ordering."""
        watchlist = [code for code in self.config.stock_list if get_market_for_stock(code) == "cn"]
        if not self.config.market_sync_a_share_full_enabled:
            return watchlist

        df = self._fetch_cn_stock_list()
        discovered = []
        if df is not None and not df.empty and "code" in df.columns:
            discovered = [str(code).strip().upper() for code in df["code"].tolist() if str(code).strip()]
        return self._prioritize_codes(watchlist, discovered)

    def _get_us_universe(self) -> List[str]:
        """Build US universe from watchlist plus configured extra symbols."""
        watchlist = [code for code in self._get_all_watchlist_codes() if get_market_for_stock(code) == "us"]
        configured = [code for code in self.config.us_stock_list if code]
        return self._prioritize_codes(watchlist, configured)

    def _get_hk_universe(self) -> List[str]:
        """Build HK universe from explicit HK pool with legacy watchlist fallback."""
        watchlist = [code for code in self._get_all_watchlist_codes() if get_market_for_stock(code) == "hk"]
        configured = [code for code in getattr(self.config, "hk_stock_list", []) if code]
        return self._prioritize_codes(watchlist, configured)

    def _fetch_cn_stock_list(self) -> Optional[pd.DataFrame]:
        """Fetch A-share stock universe from available providers."""
        from data_provider.base import DataFetcherManager

        manager = DataFetcherManager()
        for fetcher in getattr(manager, "_fetchers", []):
            if hasattr(fetcher, "get_stock_list"):
                try:
                    df = fetcher.get_stock_list()
                    if df is not None and not df.empty:
                        logger.info("Loaded CN stock universe from %s: %s", fetcher.name, len(df))
                        return df
                except Exception as exc:
                    logger.debug("Failed to fetch CN stock list from %s: %s", getattr(fetcher, "name", "?"), exc)
        return None

    @staticmethod
    def _prioritize_codes(priority_codes: Sequence[str], all_codes: Sequence[str]) -> List[str]:
        ordered: List[str] = []
        seen = set()
        for code in list(priority_codes) + list(all_codes):
            normalized = str(code).strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _prioritize_by_freshness(self, codes: Sequence[str]) -> List[str]:
        """Prefer codes with missing or older local history."""
        ordered = [str(code).strip().upper() for code in codes if str(code).strip()]
        if len(ordered) <= 1:
            return ordered

        latest_dates = self.stock_repo.get_latest_trade_dates(ordered)
        today = date.today()

        def freshness_key(code: str) -> tuple[int, int, int]:
            latest = latest_dates.get(code)
            if latest is None:
                return (0, -999999, ordered.index(code))
            lag_days = (today - latest).days
            if lag_days > 0:
                return (1, -lag_days, ordered.index(code))
            return (2, 0, ordered.index(code))

        return sorted(ordered, key=freshness_key)

    @staticmethod
    def _normalize_markets(markets: Sequence[str]) -> List[str]:
        result: List[str] = []
        for market in markets:
            normalized = str(market).strip().lower()
            if normalized in {"cn", "hk", "us"} and normalized not in result:
                result.append(normalized)
        return result or ["cn"]

    def _set_status(self, **fields: Any) -> None:
        with self._lock:
            for key, value in fields.items():
                setattr(self._status, key, value)

    def _increment_status(
        self,
        *,
        processed: int = 0,
        saved: int = 0,
        skipped: int = 0,
        errors: int = 0,
        priority_processed: int = 0,
        priority_completed: int = 0,
    ) -> None:
        with self._lock:
            self._status.processed += processed
            self._status.saved += saved
            self._status.skipped += skipped
            self._status.errors += errors
            self._status.priority_processed += priority_processed
            self._status.priority_completed += priority_completed

    # =========================================
    # 断点续传功能
    # =========================================

    def _load_checkpoint(self, market: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint for a specific market."""
        if not SYNC_CHECKPOINT_FILE.exists():
            return None

        try:
            with open(SYNC_CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                checkpoints = json.load(f)

            if market in checkpoints:
                logger.info(f"Loaded checkpoint for {market}: last_code={checkpoints[market].get('last_code')}")
                return checkpoints[market]
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")

        return None

    def _save_checkpoint(self, market: str, code: str, synced_codes: List[str]) -> None:
        """Save checkpoint for a specific market."""
        try:
            checkpoints = {}
            if SYNC_CHECKPOINT_FILE.exists():
                with open(SYNC_CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                    checkpoints = json.load(f)

            checkpoints[market] = {
                'last_code': code,
                'synced_count': len(synced_codes),
                'synced_codes': synced_codes,
                'updated_at': datetime.now().isoformat()
            }

            # Ensure parent directory exists
            SYNC_CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)

            with open(SYNC_CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
                json.dump(checkpoints, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved checkpoint for {market}: {code} (total: {len(synced_codes)})")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _clear_checkpoint(self, market: str) -> None:
        """Clear checkpoint after sync completes."""
        try:
            if SYNC_CHECKPOINT_FILE.exists():
                with open(SYNC_CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                    checkpoints = json.load(f)

                if market in checkpoints:
                    del checkpoints[market]

                    with open(SYNC_CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(checkpoints, f, ensure_ascii=False, indent=2)

                    logger.info(f"Cleared checkpoint for {market}")
        except Exception as e:
            logger.warning(f"Failed to clear checkpoint: {e}")

    # =========================================
    # 股票筛选功能（集成 StockFilter）
    # =========================================

    def _get_cn_universe_filtered(self) -> List[str]:
        """Build CN universe with filtering based on config criteria."""
        watchlist = [code for code in self.config.stock_list if get_market_for_stock(code) == "cn"]

        if not self.config.market_sync_a_share_full_enabled:
            return watchlist

        # 使用 StockFilter 进行筛选
        from data_provider.base import DataFetcherManager
        from screening.filter import StockFilter

        try:
            manager = DataFetcherManager()
            stock_filter = StockFilter(manager)

            # 从配置读取筛选参数
            filtered_df = stock_filter.filter_stocks(
                min_market_cap=self.config.market_sync_min_market_cap,
                min_turnover=self.config.market_sync_min_turnover,
                min_turnover_rate=self.config.market_sync_min_turnover_rate,
                max_turnover_rate=self.config.market_sync_max_turnover_rate,
                min_price=self.config.market_sync_min_price,
                exclude_prefixes=self.config.market_sync_exclude_prefixes,
                target_count=self.config.market_sync_target_count,
            )

            if filtered_df is not None and not filtered_df.empty and 'code' in filtered_df.columns:
                discovered = [str(code).strip().upper() for code in filtered_df["code"].tolist() if str(code).strip()]
                logger.info(f"Filtered CN universe: {len(discovered)} stocks (from config criteria)")
                return self._prioritize_codes(watchlist, discovered)

        except Exception as e:
            logger.warning(f"Failed to filter CN stocks, falling back to full universe: {e}")

        # Fallback to full universe if filtering fails
        return self._get_cn_universe()

    # =========================================
    # 跳过已同步股票功能
    # =========================================

    def _filter_fresh_codes(self, codes: List[str]) -> List[str]:
        """Filter out stocks already synced to the latest trading day."""
        codes, _ = self._filter_fresh_codes_with_map(codes)
        return codes

    def _filter_fresh_codes_with_map(self, codes: List[str]) -> tuple[List[str], Dict[str, Optional[date]]]:
        """Filter out fresh stocks and return latest dates map.

        Returns:
            tuple: (codes to sync, latest_dates map)
        """
        if not self.config.market_sync_skip_fresh:
            # 未启用跳过，返回所有股票和空映射
            codes = [c for c in codes if str(c).strip()]
            return codes, {}

        today = date.today()
        codes_to_check = [c for c in codes if str(c).strip()]

        if not codes_to_check:
            return [], {}

        # 批量获取最新交易日期
        latest_dates = self.stock_repo.get_latest_trade_dates(codes_to_check)

        fresh_count = 0
        non_fresh_codes = []
        result_map: Dict[str, Optional[date]] = {}

        for code in codes_to_check:
            latest = latest_dates.get(code)
            result_map[code] = latest  # 保存映射供后续使用

            if latest is None:
                # 无历史数据，需要同步
                non_fresh_codes.append(code)
            elif latest >= today:
                # 已同步到今天
                fresh_count += 1
            else:
                # 有历史数据但不是最新，需要同步
                non_fresh_codes.append(code)

        if fresh_count > 0:
            logger.info(f"Skip fresh data: {fresh_count} stocks already synced to latest day, {len(non_fresh_codes)} remaining")

        # 按新鲜度排序（缺失数据的优先）
        ordered = self._prioritize_by_freshness(non_fresh_codes)
        return ordered, result_map
