# -*- coding: utf-8 -*-
"""Batch fetching helpers for data providers."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

import pandas as pd

from .code_normalization import normalize_stock_code

logger = logging.getLogger(__name__)


GetDailyDataCallable = Callable[[str, Optional[str], Optional[str], int], Tuple[pd.DataFrame, str]]


def batch_get_daily_data(
    *,
    get_daily_data: GetDailyDataCallable,
    stock_codes: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 30,
    max_workers: int = 5,
    show_progress: bool = True,
) -> List[Tuple[str, pd.DataFrame, str]]:
    """Batch fetch daily data for multiple stocks with concurrent execution."""
    from tqdm import tqdm

    results = []
    errors = []
    normalized_codes = [normalize_stock_code(code) for code in stock_codes]

    logger.info(f"[批量获取] 开始并发获取 {len(normalized_codes)} 只股票数据，并发数: {max_workers}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {
            executor.submit(
                get_daily_data,
                code,
                start_date,
                end_date,
                days,
            ): code
            for code in normalized_codes
        }

        iterator = tqdm(
            as_completed(future_to_code),
            total=len(normalized_codes),
            desc="批量获取数据",
            disable=not show_progress,
        )

        for future in iterator:
            code = future_to_code[future]
            try:
                df, source = future.result()
                results.append((code, df, source))
                iterator.set_postfix_str(f"{len(results)}/{len(normalized_codes)}")
            except Exception as exc:
                error_msg = f"{code}: {str(exc)}"
                errors.append(error_msg)
                logger.error(f"[批量获取] 失败: {error_msg}")

    success_count = len(results)
    error_count = len(errors)

    if errors:
        logger.warning(
            f"[批量获取] 完成，成功: {success_count}/{len(normalized_codes)}，"
            f"失败: {error_count}"
        )
        for error in errors[:3]:
            logger.debug(f"[批量获取] 错误详情: {error}")
    else:
        logger.info(f"[批量获取] 全部成功，共 {success_count} 只股票")

    return results
