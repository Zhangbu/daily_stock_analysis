# -*- coding: utf-8 -*-
"""Web content extraction helpers for search flows."""

from __future__ import annotations

import logging
import time

from newspaper import Article, Config
from src.config import get_config
from src.search.cache_store import search_cache_store
from utils.observability import OperationTimer

logger = logging.getLogger(__name__)


def fetch_url_content(url: str, timeout: int = 5, cache_ttl: int | None = None) -> str:
    """Fetch article body content from a URL using newspaper3k."""
    resolved_ttl = get_config().article_content_cache_ttl if cache_ttl is None else cache_ttl
    cache_key = (url, timeout)
    cache_key_str = f"{url}|{timeout}"
    cached = search_cache_store.get("article_content", cache_key_str, resolved_ttl)
    if cached is not None:
        with OperationTimer(logger, "fetch_article_content", url=url, provider="newspaper", cache_hit=True) as timer:
            timer.set_message("article content cache hit")
            return cached

    with OperationTimer(logger, "fetch_article_content", url=url, provider="newspaper", cache_hit=False) as timer:
        try:
            config = Config()
            config.browser_user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
            config.request_timeout = timeout
            config.fetch_images = False
            config.memoize_articles = False

            article = Article(url, config=config, language="zh")
            article.download()
            article.parse()

            text = article.text.strip()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)[:1500]
            if resolved_ttl and text:
                search_cache_store.put("article_content", cache_key_str, text)
            return text
        except Exception as exc:
            timer.set_message(str(exc))
            logger.debug(f"Fetch content failed for {url}: {exc}")
            return ""


def clear_article_content_cache() -> None:
    """Clear in-memory article content cache."""
    search_cache_store.clear_namespace("article_content")
