# -*- coding: utf-8 -*-
"""
Unit tests for search_stock_news and search_comprehensive_intel news_max_age_days logic (Issue #296).
"""

import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Mock newspaper before search_service import (optional dependency)
if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.search_service import SearchResponse, SearchResult, SearchService
from src.search.cache_store import search_cache_store


def _fake_search_response() -> SearchResponse:
    """Return a successful SearchResponse for mocking."""
    return SearchResponse(
        query="test",
        results=[
            SearchResult(
                title="Test",
                snippet="snippet",
                url="https://example.com/1",
                source="example.com",
                published_date=None,
            )
        ],
        provider="Mock",
        success=True,
    )


class SearchNewsFreshnessTestCase(unittest.TestCase):
    """Tests for news_max_age_days in search_stock_news and search_comprehensive_intel."""

    def tearDown(self) -> None:
        search_cache_store.clear()

    def _create_service_with_mock_provider(self, news_max_age_days: int = 3):
        """Create SearchService with a mock provider that records search() calls."""
        service = SearchService(
            bocha_keys=["dummy_key"],
            news_max_age_days=news_max_age_days,
        )
        mock_search = MagicMock(return_value=_fake_search_response())
        service._providers[0].search = mock_search
        return service, mock_search

    def _create_service_with_two_mock_providers(self, news_max_age_days: int = 3):
        """Create SearchService with two providers for fallback behavior tests."""
        service = SearchService(
            bocha_keys=["dummy_key_1"],
            tavily_keys=["dummy_key_2"],
            news_max_age_days=news_max_age_days,
        )
        first_search = MagicMock()
        second_search = MagicMock()
        service._providers[0].search = first_search
        service._providers[1].search = second_search
        return service, first_search, second_search

    @patch("src.search_service.datetime")
    def test_search_stock_news_days_monday_limit_by_news_max_age(
        self, mock_dt: MagicMock
    ) -> None:
        """Monday + news_max_age_days=1 -> search_days=1 (min(3,1)=1)."""
        mock_dt.now.return_value.weekday.return_value = 0  # Monday -> weekday_days=3
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=1
        )
        service.search_stock_news("600519", "贵州茅台")
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        self.assertEqual(call_kwargs["days"], 1)

    @patch("src.search_service.datetime")
    def test_search_stock_news_days_tuesday_weekday_dominates(
        self, mock_dt: MagicMock
    ) -> None:
        """Tuesday + news_max_age_days=3 -> search_days=1 (min(1,3)=1)."""
        mock_dt.now.return_value.weekday.return_value = 1  # Tuesday -> weekday_days=1
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=3
        )
        service.search_stock_news("600519", "贵州茅台")
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        self.assertEqual(call_kwargs["days"], 1)

    @patch("src.search_service.datetime")
    def test_search_stock_news_days_monday_news_max_age_dominates(
        self, mock_dt: MagicMock
    ) -> None:
        """Monday + news_max_age_days=5 -> search_days=3 (min(3,5)=3)."""
        mock_dt.now.return_value.weekday.return_value = 0  # Monday -> weekday_days=3
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=5
        )
        service.search_stock_news("600519", "贵州茅台")
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        self.assertEqual(call_kwargs["days"], 3)

    @patch("src.search_service.datetime")
    def test_search_stock_news_days_weekend(self, mock_dt: MagicMock) -> None:
        """Saturday + news_max_age_days=5 -> search_days=2 (min(2,5)=2)."""
        mock_dt.now.return_value.weekday.return_value = 5  # Saturday -> weekday_days=2
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=5
        )
        service.search_stock_news("600519", "贵州茅台")
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        self.assertEqual(call_kwargs["days"], 2)

    def test_search_comprehensive_intel_uses_news_max_age_days(self) -> None:
        """search_comprehensive_intel passes news_max_age_days directly to provider.search."""
        service, mock_search = self._create_service_with_mock_provider(
            news_max_age_days=2
        )
        with patch("src.search_service.time.sleep"):  # avoid delay in tests
            service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="贵州茅台",
                max_searches=2,
            )
        self.assertGreaterEqual(mock_search.call_count, 1)
        for call in mock_search.call_args_list:
            call_kwargs = call[1]
            self.assertEqual(
                call_kwargs["days"],
                2,
                msg=f"Expected days=2, got {call_kwargs.get('days')}",
            )

    def test_search_stock_news_deduplicates_inflight_requests(self) -> None:
        """Concurrent identical news lookups should share one provider call."""
        service, mock_search = self._create_service_with_mock_provider(news_max_age_days=3)
        results = []
        errors = []
        start_event = threading.Event()

        def delayed_search(*args, **kwargs):
            time.sleep(0.05)
            return _fake_search_response()

        mock_search.side_effect = delayed_search

        def worker() -> None:
            try:
                start_event.wait(timeout=1)
                results.append(service.search_stock_news("600519", "贵州茅台"))
            except Exception as exc:  # pragma: no cover - defensive collection for assertions
                errors.append(exc)

        thread1 = threading.Thread(target=worker)
        thread2 = threading.Thread(target=worker)
        thread1.start()
        thread2.start()
        start_event.set()
        thread1.join()
        thread2.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(mock_search.call_count, 1)
        self.assertTrue(all(result.success for result in results))

    def test_search_comprehensive_intel_fallbacks_to_next_provider_per_dimension(self) -> None:
        """When provider-1 fails, comprehensive search should fallback to provider-2."""
        service, first_search, second_search = self._create_service_with_two_mock_providers(news_max_age_days=2)
        first_search.return_value = SearchResponse(
            query="q",
            results=[],
            provider="P1",
            success=False,
            error_message="p1 down",
        )
        second_search.return_value = _fake_search_response()

        with patch("src.search_service.time.sleep"):
            results = service.search_comprehensive_intel(
                stock_code="600519",
                stock_name="贵州茅台",
                max_searches=1,
            )

        self.assertIn("latest_news", results)
        self.assertTrue(results["latest_news"].success)
        self.assertGreaterEqual(first_search.call_count, 1)
        self.assertGreaterEqual(second_search.call_count, 1)
