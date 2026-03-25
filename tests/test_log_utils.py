# -*- coding: utf-8 -*-
"""Tests for logging utility helpers."""

import unittest

from utils.log_utils import build_log_context


class LogUtilsTestCase(unittest.TestCase):
    def test_build_log_context_skips_empty_values(self):
        context = build_log_context(query_id="q1", stock_code="600519", provider=None, cache_hit="")
        self.assertEqual(context, "[query_id=q1 stock_code=600519]")

    def test_build_log_context_empty(self):
        self.assertEqual(build_log_context(provider=None), "")


if __name__ == "__main__":
    unittest.main()
