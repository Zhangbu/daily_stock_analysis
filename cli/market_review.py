# -*- coding: utf-8 -*-
"""
===================================
CLI 模式: 仅大盘复盘
===================================
"""
import logging

from src.config import Config

logger = logging.getLogger(__name__)


def handle_market_review(args, config: Config) -> int:
    from src.analyzer import GeminiAnalyzer
    from src.core.market_review import run_market_review
    from src.notification import NotificationService
    from src.search_service import SearchService

    # Issue #373: Trading day check for market-review-only mode.
    effective_region = None
    if not getattr(args, "force_run", False) and getattr(config, "trading_day_check_enabled", True):
        from src.core.trading_calendar import (
            get_open_markets_today,
            compute_effective_region as _compute_region,
        )

        open_markets = get_open_markets_today()
        effective_region = _compute_region(
            getattr(config, "market_review_region", "cn") or "cn", open_markets
        )
        if effective_region == "":
            logger.info("今日大盘复盘相关市场均为非交易日，跳过执行。可使用 --force-run 强制执行。")
            return 0

    logger.info("模式: 仅大盘复盘")
    notifier = NotificationService()

    search_service = None
    analyzer = None

    if config.has_search_capability_enabled():
        search_service = SearchService(
            bocha_keys=config.bocha_api_keys,
            tavily_keys=config.tavily_api_keys,
            anspire_keys=config.anspire_api_keys,
            brave_keys=config.brave_api_keys,
            serpapi_keys=config.serpapi_keys,
            minimax_keys=config.minimax_api_keys,
            searxng_base_urls=config.searxng_base_urls,
            searxng_public_instances_enabled=config.searxng_public_instances_enabled,
            news_max_age_days=config.news_max_age_days,
            news_strategy_profile=getattr(config, "news_strategy_profile", "short"),
        )

    if config.gemini_api_key or config.openai_api_key:
        analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)
        if not analyzer.is_available():
            logger.warning("AI 分析器初始化后不可用，请检查 API Key 配置")
            analyzer = None
    else:
        logger.warning("未检测到 API Key (Gemini/OpenAI)，将仅使用模板生成报告")

    run_market_review(
        notifier=notifier,
        analyzer=analyzer,
        search_service=search_service,
        send_notification=not args.no_notify,
        override_region=effective_region,
    )
    return 0
