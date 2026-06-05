# -*- coding: utf-8 -*-
"""
===================================
CLI 模式: 回测
===================================
"""
import logging

logger = logging.getLogger(__name__)


def handle_backtest(args) -> int:
    logger.info("模式: 回测")
    from src.services.backtest_service import BacktestService

    service = BacktestService()
    stats = service.run_backtest(
        code=getattr(args, "backtest_code", None),
        force=getattr(args, "backtest_force", False),
        eval_window_days=getattr(args, "backtest_days", None),
    )
    logger.info(
        f"回测完成: processed={stats.get('processed')} "
        f"saved={stats.get('saved')} completed={stats.get('completed')} "
        f"insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
    )
    return 0
