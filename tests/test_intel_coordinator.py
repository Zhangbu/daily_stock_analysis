# -*- coding: utf-8 -*-
"""Tests for extracted intel coordinator."""

import unittest
from unittest.mock import Mock

from src.core.intel_coordinator import IntelCoordinator


class IntelCoordinatorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.search_service = Mock()
        self.search_service.is_available = True
        self.persistence = Mock()
        self.query_context_builder = Mock(return_value={"query_id": "q1"})
        self.coordinator = IntelCoordinator(
            search_service=self.search_service,
            persistence=self.persistence,
            build_query_context=self.query_context_builder,
        )

    def test_collect_comprehensive_intel_formats_and_persists(self):
        response = Mock(success=True, results=[Mock()], query="q")
        self.search_service.search_comprehensive_intel.return_value = {"latest_news": response}
        self.search_service.format_intel_report.return_value = "formatted-intel"

        news_context = self.coordinator.collect_comprehensive_intel(
            code="600519",
            stock_name="贵州茅台",
            query_id="q1",
            max_searches=3,
        )

        self.assertEqual(news_context, "formatted-intel")
        self.search_service.search_comprehensive_intel.assert_called_once_with(
            stock_code="600519",
            stock_name="贵州茅台",
            max_searches=3,
        )
        self.persistence.save_news_intel.assert_called_once()

    def test_collect_comprehensive_intel_returns_none_when_unavailable(self):
        self.search_service.is_available = False

        news_context = self.coordinator.collect_comprehensive_intel(
            code="600519",
            stock_name="贵州茅台",
            query_id="q1",
        )

        self.assertIsNone(news_context)
        self.search_service.search_comprehensive_intel.assert_not_called()

    def test_persist_latest_news_for_agent_uses_latest_news_dimension(self):
        response = Mock(success=True, results=[Mock(), Mock()], query="latest")
        self.search_service.search_stock_news.return_value = response

        self.coordinator.persist_latest_news_for_agent(
            code="600519",
            stock_name="贵州茅台",
            query_id="q1",
            max_results=2,
        )

        self.search_service.search_stock_news.assert_called_once_with(
            stock_code="600519",
            stock_name="贵州茅台",
            max_results=2,
        )
        self.persistence.save_news_intel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
