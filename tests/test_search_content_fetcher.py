# -*- coding: utf-8 -*-
"""Tests for extracted search content fetching helpers."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.search.content_fetcher import clear_article_content_cache, fetch_url_content


class SearchContentFetcherTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        clear_article_content_cache()

    def test_fetch_url_content_normalizes_lines_and_truncates(self):
        fake_article = SimpleNamespace(
            download=MagicMock(),
            parse=MagicMock(),
            text=" line1 \n\n line2 \n",
        )

        with patch("src.search.content_fetcher.Config") as mock_config, patch(
            "src.search.content_fetcher.Article", return_value=fake_article
        ):
            mock_config.return_value = SimpleNamespace()
            content = fetch_url_content("https://example.com", timeout=3)

        self.assertEqual(content, "line1\nline2")

    def test_fetch_url_content_uses_in_memory_cache(self):
        fake_article = SimpleNamespace(
            download=MagicMock(),
            parse=MagicMock(),
            text="line1",
        )

        with patch("src.search.content_fetcher.Config") as mock_config, patch(
            "src.search.content_fetcher.Article", return_value=fake_article
        ) as mock_article:
            mock_config.return_value = SimpleNamespace()
            first = fetch_url_content("https://example.com", timeout=3, cache_ttl=30)
            second = fetch_url_content("https://example.com", timeout=3, cache_ttl=30)

        self.assertEqual(first, "line1")
        self.assertEqual(second, "line1")
        mock_article.assert_called_once()

    def test_fetch_url_content_returns_empty_on_error(self):
        with patch("src.search.content_fetcher.Article", side_effect=RuntimeError("boom")):
            content = fetch_url_content("https://example.com")

        self.assertEqual(content, "")


if __name__ == "__main__":
    unittest.main()
