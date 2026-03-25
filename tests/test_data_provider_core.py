# -*- coding: utf-8 -*-
"""Tests for extracted data provider core helpers."""

import unittest

from data_provider.core.code_normalization import canonical_stock_code, normalize_stock_code


class CodeNormalizationTestCase(unittest.TestCase):
    def test_normalize_exchange_prefix(self):
        self.assertEqual(normalize_stock_code("SH600519"), "600519")
        self.assertEqual(normalize_stock_code("sz000001"), "000001")

    def test_normalize_exchange_suffix(self):
        self.assertEqual(normalize_stock_code("600519.SH"), "600519")
        self.assertEqual(normalize_stock_code("000001.SZ"), "000001")

    def test_normalize_keeps_non_a_share_codes(self):
        self.assertEqual(normalize_stock_code("HK00700"), "HK00700")
        self.assertEqual(normalize_stock_code("AAPL"), "AAPL")

    def test_canonical_stock_code(self):
        self.assertEqual(canonical_stock_code(" aapl "), "AAPL")
        self.assertEqual(canonical_stock_code("hk00700"), "HK00700")
        self.assertEqual(canonical_stock_code("600519"), "600519")


if __name__ == "__main__":
    unittest.main()
