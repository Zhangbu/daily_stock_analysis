# -*- coding: utf-8 -*-
"""Background market data sync service for CN/US stock universes."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from src.config import Config, get_config
from src.core.trading_calendar import get_market_for_stock
from src.repositories.stock_repo import StockRepository
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)


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
                for code in self.config.stock_list
                if get_market_for_stock(code) in set(markets)
            }
            self._set_status(priority_candidates=len(priority_codes))
            for market in markets:
                self._set_status(current_market=market, message=f"syncing {market} market")
                codes = self._get_market_universe(market)
                self._set_status(total_candidates=self._status.total_candidates + len(codes))

                for code in codes:
                    self._set_status(current_code=code)
                    is_priority = code in priority_codes
                    try:
                        saved = self._sync_single_code(code)
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

    def _sync_single_code(self, code: str) -> int:
        """Sync one stock code with incremental fallback when history already exists."""
        from data_provider.base import DataFetcherManager

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

    def _get_market_universe(self, market: str) -> List[str]:
        """Resolve prioritized stock universe for one market."""
        if market == "cn":
            codes = self._get_cn_universe()
        elif market == "us":
            codes = self._get_us_universe()
        else:
            codes = []

        max_codes = int(self.config.market_sync_max_codes_per_run)
        if max_codes > 0:
            codes = codes[:max_codes]
        return self._prioritize_by_freshness(codes)

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
        watchlist = [code for code in self.config.stock_list if get_market_for_stock(code) == "us"]
        configured = [code for code in self.config.us_stock_list if code]
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
            if normalized in {"cn", "us"} and normalized not in result:
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
