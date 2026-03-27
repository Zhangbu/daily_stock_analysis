# -*- coding: utf-8 -*-
"""Tests for optional API router feature toggles."""

import importlib
import os
import unittest

from src.config import Config


class ApiRouterFeatureTogglesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {k: os.environ.get(k) for k in self._toggle_keys()}

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        Config.reset_instance()

    @staticmethod
    def _toggle_keys():
        return [
            "ENABLE_AGENT_API",
            "ENABLE_BACKTEST_API",
            "ENABLE_STRATEGY_BACKTEST_API",
            "ENABLE_MARKET_SYNC_API",
            "ENABLE_SCREENING_API",
        ]

    def test_optional_routes_are_not_registered_when_disabled(self) -> None:
        os.environ["ENABLE_AGENT_API"] = "false"
        os.environ["ENABLE_BACKTEST_API"] = "false"
        os.environ["ENABLE_STRATEGY_BACKTEST_API"] = "false"
        os.environ["ENABLE_MARKET_SYNC_API"] = "false"
        os.environ["ENABLE_SCREENING_API"] = "false"
        Config.reset_instance()

        router_module = importlib.import_module("api.v1.router")
        router_module = importlib.reload(router_module)
        paths = {route.path for route in router_module.router.routes}

        self.assertNotIn("/api/v1/agent/chat", paths)
        self.assertNotIn("/api/v1/backtest/results", paths)
        self.assertNotIn("/api/v1/strategy-backtest/strategies", paths)
        self.assertNotIn("/api/v1/system/market-sync/status", paths)
        self.assertNotIn("/api/v1/screening/filter", paths)


if __name__ == "__main__":
    unittest.main()
