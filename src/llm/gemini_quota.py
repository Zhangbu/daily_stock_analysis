# -*- coding: utf-8 -*-
"""In-process Gemini quota controller (per-model RPM and daily limit)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Optional


@dataclass
class GeminiQuotaDecision:
    """Decision returned by quota acquisition."""

    acquired: bool
    reason: Optional[str] = None  # None / "rpm" / "daily"
    wait_seconds: float = 0.0


class GeminiQuotaController:
    """Per-process quota tracker for Gemini models."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._minute_calls: Dict[str, Deque[float]] = defaultdict(deque)
        self._daily_counts: Dict[str, int] = defaultdict(int)
        self._daily_day: Dict[str, str] = defaultdict(self._today)

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def reset(self) -> None:
        """Reset runtime counters (mainly for tests)."""
        with self._lock:
            self._minute_calls.clear()
            self._daily_counts.clear()
            self._daily_day.clear()

    def acquire(
        self,
        model_name: str,
        per_minute: int,
        daily_limit: int,
        now: Optional[float] = None,
    ) -> GeminiQuotaDecision:
        """Try to reserve one Gemini request slot for a specific model."""
        if not model_name:
            return GeminiQuotaDecision(acquired=True)

        now_ts = time.time() if now is None else now
        per_minute = max(1, int(per_minute or 1))
        daily_limit = max(1, int(daily_limit or 1))

        with self._lock:
            today = self._today()
            if self._daily_day[model_name] != today:
                self._daily_day[model_name] = today
                self._daily_counts[model_name] = 0
                self._minute_calls[model_name].clear()

            calls = self._minute_calls[model_name]
            while calls and now_ts - calls[0] >= 60:
                calls.popleft()

            if self._daily_counts[model_name] >= daily_limit:
                return GeminiQuotaDecision(acquired=False, reason="daily", wait_seconds=0.0)

            if len(calls) >= per_minute:
                wait_seconds = max(0.05, 60 - (now_ts - calls[0]) + 0.05)
                return GeminiQuotaDecision(acquired=False, reason="rpm", wait_seconds=wait_seconds)

            calls.append(now_ts)
            self._daily_counts[model_name] += 1
            return GeminiQuotaDecision(acquired=True)


_quota_controller = GeminiQuotaController()


def get_gemini_quota_controller() -> GeminiQuotaController:
    """Global singleton accessor."""
    return _quota_controller
