# -*- coding: utf-8 -*-
"""Tests for Gemini per-model quota controller."""

import unittest

from src.llm.gemini_quota import GeminiQuotaController


class GeminiQuotaControllerTestCase(unittest.TestCase):
    def test_per_model_rpm_and_daily_limits(self) -> None:
        limiter = GeminiQuotaController()
        model = "gemini-3-flash-preview"

        d1 = limiter.acquire(model_name=model, per_minute=2, daily_limit=3, now=0.0)
        d2 = limiter.acquire(model_name=model, per_minute=2, daily_limit=3, now=1.0)
        d3 = limiter.acquire(model_name=model, per_minute=2, daily_limit=3, now=2.0)

        self.assertTrue(d1.acquired)
        self.assertTrue(d2.acquired)
        self.assertFalse(d3.acquired)
        self.assertEqual(d3.reason, "rpm")
        self.assertGreater(d3.wait_seconds, 0)

        # minute window moved forward, third request should become available
        d4 = limiter.acquire(model_name=model, per_minute=2, daily_limit=3, now=61.0)
        self.assertTrue(d4.acquired)

        # daily limit reached
        d5 = limiter.acquire(model_name=model, per_minute=2, daily_limit=3, now=62.0)
        self.assertFalse(d5.acquired)
        self.assertEqual(d5.reason, "daily")

    def test_models_are_isolated(self) -> None:
        limiter = GeminiQuotaController()

        a1 = limiter.acquire(model_name="gemini-3-flash-preview", per_minute=1, daily_limit=1, now=0.0)
        b1 = limiter.acquire(model_name="gemini-2.5-flash", per_minute=1, daily_limit=1, now=0.0)

        self.assertTrue(a1.acquired)
        self.assertTrue(b1.acquired)

        a2 = limiter.acquire(model_name="gemini-3-flash-preview", per_minute=1, daily_limit=1, now=1.0)
        b2 = limiter.acquire(model_name="gemini-2.5-flash", per_minute=1, daily_limit=1, now=1.0)

        self.assertFalse(a2.acquired)
        self.assertEqual(a2.reason, "daily")
        self.assertFalse(b2.acquired)
        self.assertEqual(b2.reason, "daily")


if __name__ == "__main__":
    unittest.main()
