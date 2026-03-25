# -*- coding: utf-8 -*-
"""Provider routing helpers for data fetch orchestration."""

from __future__ import annotations

import logging
from typing import Iterable, Optional, Tuple

import pandas as pd

from .code_normalization import normalize_stock_code

logger = logging.getLogger(__name__)


def route_daily_data(
    *,
    fetchers: Iterable,
    data_fetch_error_cls,
    stock_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 30,
) -> Tuple[pd.DataFrame, str]:
    """Route daily data requests through fetchers with fallback behavior."""
    from data_provider.us_index_mapping import is_us_index_code, is_us_stock_code

    normalized_code = normalize_stock_code(stock_code)
    fetcher_list = list(fetchers)
    errors = []

    if is_us_index_code(normalized_code) or is_us_stock_code(normalized_code):
        return _route_us_daily_data(
            fetchers=fetcher_list,
            data_fetch_error_cls=data_fetch_error_cls,
            stock_code=normalized_code,
            start_date=start_date,
            end_date=end_date,
            days=days,
            errors=errors,
        )

    for fetcher in fetcher_list:
        try:
            logger.info(f"尝试使用 [{fetcher.name}] 获取 {normalized_code}...")
            df = fetcher.get_daily_data(
                stock_code=normalized_code,
                start_date=start_date,
                end_date=end_date,
                days=days,
            )
            if df is not None and not df.empty:
                logger.info(f"[{fetcher.name}] 成功获取 {normalized_code}")
                return df, fetcher.name
        except Exception as exc:
            error_msg = f"[{fetcher.name}] 失败: {str(exc)}"
            logger.warning(error_msg)
            errors.append(error_msg)

    error_summary = f"所有数据源获取 {normalized_code} 失败:\n" + "\n".join(errors)
    logger.error(error_summary)
    raise data_fetch_error_cls(error_summary)


def _route_us_daily_data(
    *,
    fetchers,
    data_fetch_error_cls,
    stock_code: str,
    start_date: Optional[str],
    end_date: Optional[str],
    days: int,
    errors,
) -> Tuple[pd.DataFrame, str]:
    """Route US stocks and indices directly to Yfinance."""
    for fetcher in fetchers:
        if fetcher.name != "YfinanceFetcher":
            continue

        try:
            logger.info(f"[{fetcher.name}] 美股/美股指数 {stock_code} 直接路由...")
            df = fetcher.get_daily_data(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                days=days,
            )
            if df is not None and not df.empty:
                logger.info(f"[{fetcher.name}] 成功获取 {stock_code}")
                return df, fetcher.name
        except Exception as exc:
            error_msg = f"[{fetcher.name}] 失败: {str(exc)}"
            logger.warning(error_msg)
            errors.append(error_msg)
        break

    error_summary = f"美股/美股指数 {stock_code} 获取失败:\n" + "\n".join(errors)
    logger.error(error_summary)
    raise data_fetch_error_cls(error_summary)
