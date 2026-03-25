# -*- coding: utf-8 -*-
"""Tests for market sync endpoints."""

import unittest
from unittest.mock import MagicMock

from api.v1.endpoints.market_sync import get_market_sync_status, run_market_sync
from api.v1.schemas.market_sync import MarketSyncRunRequest


class MarketSyncEndpointTestCase(unittest.TestCase):
    def test_get_market_sync_status_returns_status(self) -> None:
        service = MagicMock()
        service.get_status.return_value = {
            "running": False,
            "started_at": None,
            "finished_at": None,
            "current_market": None,
            "current_code": None,
            "processed": 0,
            "saved": 0,
            "skipped": 0,
            "errors": 0,
            "total_candidates": 0,
            "priority_candidates": 0,
            "priority_processed": 0,
            "priority_completed": 0,
            "message": "idle",
            "markets": ["cn"],
        }

        payload = get_market_sync_status(service)

        self.assertFalse(payload.running)
        self.assertEqual(payload.markets, ["cn"])

    def test_run_market_sync_returns_accepted_response(self) -> None:
        service = MagicMock()
        service.start_background_sync.return_value = True
        service.get_status.return_value = {
            "running": True,
            "started_at": "2026-03-16T00:00:00",
            "finished_at": None,
            "current_market": "cn",
            "current_code": None,
            "processed": 0,
            "saved": 0,
            "skipped": 0,
            "errors": 0,
            "total_candidates": 100,
            "priority_candidates": 12,
            "priority_processed": 5,
            "priority_completed": 4,
            "message": "sync started",
            "markets": ["cn", "us"],
        }

        payload = run_market_sync(MarketSyncRunRequest(markets=["cn", "us"]), service)

        self.assertTrue(payload.accepted)
        self.assertTrue(payload.status.running)


if __name__ == "__main__":
    unittest.main()
