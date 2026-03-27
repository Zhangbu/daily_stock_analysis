# -*- coding: utf-8 -*-
"""Tests for Tushare fetcher initialization behavior."""

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


class TushareFetcherInitTestCase(unittest.TestCase):
    def test_init_api_uses_direct_token_without_writing_file(self) -> None:
        fake_api = MagicMock()
        fake_tushare = ModuleType("tushare")
        fake_tushare.pro_api = MagicMock(return_value=fake_api)
        fake_tushare.set_token = MagicMock()

        fake_config = SimpleNamespace(tushare_token="test-token")

        with patch.dict(sys.modules, {"tushare": fake_tushare}):
            from data_provider.tushare_fetcher import TushareFetcher

            with patch("data_provider.tushare_fetcher.get_config", return_value=fake_config):
                fetcher = TushareFetcher()

        self.assertIs(fetcher._api, fake_api)
        fake_tushare.pro_api.assert_called_once_with("test-token")
        fake_tushare.set_token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
