# -*- coding: utf-8 -*-
"""Parallel input collection helpers for stock analysis pipeline."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, Tuple


class ParallelAnalysisInputCollector:
    """Collect trend and intel inputs concurrently with fault tolerance."""

    def __init__(self, *, logger: logging.Logger) -> None:
        self.logger = logger

    def collect(
        self,
        *,
        code: str,
        trend_task: Callable[[], Any],
        intel_task: Callable[[], Any],
        log_stage_latency: Callable[[str, float], None],
    ) -> Tuple[Optional[Any], str]:
        """Run trend/intel tasks concurrently and return normalized outputs."""
        trend_result: Optional[Any] = None
        news_context = ""
        started_at = {
            "trend": time.perf_counter(),
            "intel": time.perf_counter(),
        }

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                "trend": executor.submit(trend_task),
                "intel": executor.submit(intel_task),
            }

            for name, future in futures.items():
                try:
                    value = future.result()
                    if name == "trend":
                        trend_result = value
                    else:
                        news_context = value or ""
                    log_stage_latency(name, started_at[name])
                except Exception as exc:
                    log_stage_latency(f"{name}_failed", started_at[name])
                    if name == "trend":
                        self.logger.warning(f"[{code}] 趋势分析失败: {exc}", exc_info=True)
                    else:
                        self.logger.warning(f"[{code}] 情报搜索失败: {exc}", exc_info=True)

        return trend_result, news_context
