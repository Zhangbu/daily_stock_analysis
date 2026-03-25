# -*- coding: utf-8 -*-
"""Tests for extracted news intel repository."""

import unittest
from unittest.mock import Mock

from src.repositories.news_repo import NewsIntelRepository


class NewsIntelRepositoryTestCase(unittest.TestCase):
    def test_save_delegates_to_db(self):
        db = Mock()
        db.save_news_intel.return_value = 1
        repo = NewsIntelRepository(db)

        saved = repo.save(
            code="600519",
            name="贵州茅台",
            dimension="latest_news",
            query="贵州茅台 最新消息",
            response=Mock(),
            query_context={"query_id": "q1"},
        )

        self.assertEqual(saved, 1)
        db.save_news_intel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
