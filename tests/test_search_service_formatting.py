# -*- coding: utf-8 -*-
"""Tests for compact intel report formatting."""

import unittest

from src.search_service import SearchResponse, SearchResult, SearchService


class SearchServiceFormattingTestCase(unittest.TestCase):
    def test_format_intel_report_limits_results_and_snippet_length(self) -> None:
        service = SearchService()
        long_snippet = "A" * 200
        results = [
            SearchResult(
                title=f"新闻{i}",
                snippet=long_snippet,
                url=f"https://example.com/{i}",
                source="example.com",
                published_date="2026-03-30",
            )
            for i in range(1, 4)
        ]
        response = SearchResponse(
            query="腾讯控股 最新消息",
            results=results,
            provider="mock",
            success=True,
        )

        report = service.format_intel_report({"latest_news": response}, "腾讯控股")

        self.assertIn("1. 新闻1", report)
        self.assertIn("2. 新闻2", report)
        self.assertNotIn("3. 新闻3", report)
        self.assertNotIn("A" * 120, report)


if __name__ == "__main__":
    unittest.main()
