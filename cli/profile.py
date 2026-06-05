# -*- coding: utf-8 -*-
"""
===================================
CLI 模式: 策略画像运行
===================================
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def handle_profile(args, stock_codes: Optional[list[str]]) -> int:
    logger.info("模式: 策略画像分析")
    from src.services.profile_strategy_service import ProfileStrategyService

    service = ProfileStrategyService(
        profile_name=args.profile,
        strategy_name=getattr(args, "strategy", None),
    )
    results = service.run(stocks_override=stock_codes)
    logger.info("\n%s", service.format_report(results))
    return 0
