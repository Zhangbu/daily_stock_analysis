# -*- coding: utf-8 -*-
"""Rate limiting helpers for data providers."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Unified API request rate limiter using token bucket algorithm."""

    def __init__(
        self,
        calls_per_minute: int = 60,
        min_interval: float = 0.0,
        name: str = "RateLimiter",
    ):
        self.calls_per_minute = calls_per_minute
        self.min_interval = min_interval
        self.name = name

        self._tokens = float(calls_per_minute)
        self._max_tokens = float(calls_per_minute)
        self._refill_rate = calls_per_minute / 60.0

        self._last_refill_time = time.time()
        self._last_request_time: Optional[float] = None
        self._lock = threading.Lock()

        logger.debug(
            f"[{self.name}] Initialized: {calls_per_minute} calls/min, "
            f"min_interval={min_interval}s"
        )

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill_time

        if elapsed > 0:
            new_tokens = elapsed * self._refill_rate
            self._tokens = min(self._max_tokens, self._tokens + new_tokens)
            self._last_refill_time = now

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire permission to make a request."""
        start_time = time.time()

        while True:
            with self._lock:
                self._refill_tokens()
                now = time.time()

                if self._last_request_time is not None and self.min_interval > 0:
                    time_since_last = now - self._last_request_time
                    if time_since_last < self.min_interval:
                        wait_time = self.min_interval - time_since_last
                        logger.debug(
                            f"[{self.name}] Min interval not met, waiting {wait_time:.2f}s"
                        )
                    else:
                        wait_time = 0
                else:
                    wait_time = 0

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self._last_request_time = now
                    logger.debug(
                        f"[{self.name}] Token acquired, "
                        f"remaining: {self._tokens:.1f}/{self._max_tokens:.0f}"
                    )
                    return True

                tokens_needed = 1.0 - self._tokens
                refill_wait = tokens_needed / self._refill_rate
                total_wait = max(wait_time, refill_wait)

                if timeout is not None:
                    elapsed = now - start_time
                    if elapsed + total_wait > timeout:
                        return False

                logger.debug(
                    f"[{self.name}] Rate limit reached, waiting {total_wait:.2f}s for token refill"
                )

            time.sleep(total_wait)

    def try_acquire(self) -> bool:
        """Try to acquire without blocking."""
        with self._lock:
            self._refill_tokens()
            now = time.time()

            if self._last_request_time is not None and self.min_interval > 0:
                if now - self._last_request_time < self.min_interval:
                    return False

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self._last_request_time = now
                return True

            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        with self._lock:
            self._refill_tokens()
            return {
                "name": self.name,
                "tokens_available": round(self._tokens, 2),
                "max_tokens": self._max_tokens,
                "calls_per_minute": self.calls_per_minute,
                "min_interval": self.min_interval,
            }
