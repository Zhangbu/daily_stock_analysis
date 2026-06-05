# -*- coding: utf-8 -*-
"""
===================================
CLI 模式: 单次运行
===================================
"""
import logging
import time
from typing import Optional

from src.config import Config
from src.core.runner import run_full_analysis

logger = logging.getLogger(__name__)


def handle_analyze(
    args,
    config: Config,
    stock_codes: Optional[list[str]],
    serve_started: bool,
) -> int:
    # 正常单次运行
    if config.run_immediately:
        run_full_analysis(config, args, stock_codes)
    else:
        logger.info("配置为不立即运行分析 (RUN_IMMEDIATELY=false)")

    logger.info("\n程序执行完成")

    # 如果启用了服务，保持程序运行
    if serve_started and not (args.schedule or config.schedule_enabled):
        logger.info("API 服务运行中 (按 Ctrl+C 退出)...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    return 0
