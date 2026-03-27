# -*- coding: utf-8 -*-
"""Regression tests for Yahoo realtime quote integration."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch


if "fake_useragent" not in sys.modules:
    sys.modules["fake_useragent"] = MagicMock()


class TestYfinanceRealtimeQuotes(unittest.TestCase):
    def test_get_stock_name_reads_yfinance_metadata(self):
        from data_provider.yfinance_fetcher import YfinanceFetcher

        mock_ticker = MagicMock()
        mock_ticker.info = {"shortName": "Tencent Holdings"}
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        fetcher = YfinanceFetcher()
        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            name = fetcher.get_stock_name("hk00700")

        self.assertEqual(mock_yf.Ticker.call_args[0][0], "0700.HK")
        self.assertEqual(name, "Tencent Holdings")

    def test_hk_quote_uses_yfinance_symbol_conversion(self):
        from data_provider.realtime_types import RealtimeSource
        from data_provider.yfinance_fetcher import YfinanceFetcher

        mock_ticker = MagicMock()
        mock_ticker.fast_info = {
            "lastPrice": 320.5,
            "previousClose": 315.0,
            "open": 318.0,
            "dayHigh": 321.0,
            "dayLow": 317.2,
            "lastVolume": 1234567,
            "marketCap": 987654321.0,
        }
        mock_ticker.info = {"shortName": "Tencent Holdings"}

        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        fetcher = YfinanceFetcher()
        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            quote = fetcher.get_realtime_quote("hk00700")

        self.assertIsNotNone(quote)
        self.assertEqual(mock_yf.Ticker.call_args[0][0], "0700.HK")
        self.assertEqual(quote.code, "HK00700")
        self.assertEqual(quote.name, "Tencent Holdings")
        self.assertEqual(quote.source, RealtimeSource.YFINANCE)
        self.assertEqual(quote.price, 320.5)
        self.assertEqual(quote.pre_close, 315.0)
        self.assertEqual(quote.volume, 1234567)
        self.assertIsNotNone(quote.amount)

    def test_realtime_priority_accepts_yfinance_source(self):
        from src.config import Config
        from data_provider.base import DataFetcherManager
        from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource

        class _StubYfinanceFetcher:
            name = "YfinanceFetcher"
            priority = 0

            def get_realtime_quote(self, stock_code: str):
                return UnifiedRealtimeQuote(
                    code=stock_code,
                    name="Tencent Holdings",
                    source=RealtimeSource.YFINANCE,
                    price=320.5,
                )

        with patch.dict(
            os.environ,
            {
                "ENABLE_REALTIME_QUOTE": "true",
                "REALTIME_SOURCE_PRIORITY": "yfinance",
            },
            clear=False,
        ):
            Config._instance = None
            manager = DataFetcherManager(fetchers=[_StubYfinanceFetcher()])
            quote = manager.get_realtime_quote("hk00700")

        Config._instance = None
        self.assertIsNotNone(quote)
        self.assertEqual(quote.source, RealtimeSource.YFINANCE)
        self.assertEqual(quote.code, "HK00700")


if __name__ == "__main__":
    unittest.main()
