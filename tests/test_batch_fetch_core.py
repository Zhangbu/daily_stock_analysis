# -*- coding: utf-8 -*-
"""Tests for extracted batch fetch helper."""

import unittest

import pandas as pd

from data_provider.core.batch_fetch import batch_get_daily_data


class BatchFetchHelperTestCase(unittest.TestCase):
    def test_batch_fetch_normalizes_codes_and_collects_results(self):
        calls = []

        def fake_get_daily_data(code, start_date, end_date, days):
            calls.append((code, start_date, end_date, days))
            return pd.DataFrame({"code": [code]}), "fake"

        results = batch_get_daily_data(
            get_daily_data=fake_get_daily_data,
            stock_codes=["SH600519", "aapl"],
            days=20,
            max_workers=2,
            show_progress=False,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(sorted(code for code, _, _ in results), ["600519", "aapl"])
        self.assertEqual(calls[0][3], 20)
        self.assertIn(("600519", None, None, 20), calls)

    def test_batch_fetch_keeps_partial_success(self):
        def fake_get_daily_data(code, start_date, end_date, days):
            if code == "000001":
                raise RuntimeError("boom")
            return pd.DataFrame({"code": [code]}), "fake"

        results = batch_get_daily_data(
            get_daily_data=fake_get_daily_data,
            stock_codes=["000001", "600519"],
            max_workers=2,
            show_progress=False,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "600519")


if __name__ == "__main__":
    unittest.main()
