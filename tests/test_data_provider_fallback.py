# -*- coding: utf-8 -*-
"""Regression tests for DataFetcherManager fallback behavior."""

import unittest

import pandas as pd

from data_provider.base import BaseFetcher, DataFetchError, DataFetcherManager


class _FailingFetcher(BaseFetcher):
    name = "FailingFetcher"
    priority = 0

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise RuntimeError("should not be called")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        return df

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30) -> pd.DataFrame:
        raise RuntimeError("boom")


class _SuccessFetcher(BaseFetcher):
    name = "SuccessFetcher"
    priority = 1

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise RuntimeError("should not be called")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        return df

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame({"code": [stock_code], "close": [1.0]})


class _YfinanceFetcher(_SuccessFetcher):
    name = "YfinanceFetcher"
    priority = 99


class DataProviderFallbackTestCase(unittest.TestCase):
    def test_get_daily_data_falls_back_to_next_fetcher(self):
        manager = DataFetcherManager(fetchers=[_FailingFetcher(), _SuccessFetcher()])

        df, source = manager.get_daily_data("SH600519", days=10)

        self.assertEqual(source, "SuccessFetcher")
        self.assertEqual(df.iloc[0]["code"], "600519")

    def test_get_daily_data_raises_when_all_fetchers_fail(self):
        manager = DataFetcherManager(fetchers=[_FailingFetcher()])

        with self.assertRaises(DataFetchError):
            manager.get_daily_data("600519", days=10)

    def test_us_stock_routes_directly_to_yfinance(self):
        manager = DataFetcherManager(fetchers=[_FailingFetcher(), _YfinanceFetcher()])

        df, source = manager.get_daily_data("AAPL", days=10)

        self.assertEqual(source, "YfinanceFetcher")
        self.assertEqual(df.iloc[0]["code"], "AAPL")


if __name__ == "__main__":
    unittest.main()
