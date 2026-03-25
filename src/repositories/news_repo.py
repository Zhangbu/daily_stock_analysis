# -*- coding: utf-8 -*-
"""
===================================
新闻情报数据访问层
===================================

职责：
1. 封装新闻情报相关数据库操作
2. 提供保存与查询接口
"""

import logging
from typing import Dict, Optional

from src.storage import DatabaseManager, NewsIntel

logger = logging.getLogger(__name__)


class NewsIntelRepository:
    """封装 NewsIntel 表的数据库操作。"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save(
        self,
        *,
        code: str,
        name: str,
        dimension: str,
        query: str,
        response,
        query_context: Optional[Dict[str, str]] = None,
    ) -> int:
        """Persist fetched news intel entries."""
        try:
            return self.db.save_news_intel(
                code=code,
                name=name,
                dimension=dimension,
                query=query,
                response=response,
                query_context=query_context,
            )
        except Exception as exc:
            logger.error(f"保存新闻情报失败: {exc}")
            return 0

    def get_recent(self, *, code: str, days: int = 7, limit: int = 20):
        """Return recent news intel entries for a stock."""
        try:
            return self.db.get_recent_news(code=code, days=days, limit=limit)
        except Exception as exc:
            logger.error(f"获取新闻情报失败: {exc}")
            return []
