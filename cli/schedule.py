# -*- coding: utf-8 -*-
"""
===================================
CLI 模式: 定时任务
===================================
"""
import logging
from typing import Optional

from src.config import Config
from src.core.runner import (
    run_full_analysis,
    resolve_scheduled_stock_codes,
    build_schedule_time_provider,
    reload_runtime_config,
)

logger = logging.getLogger(__name__)


def handle_schedule(args, config: Config, stock_codes: Optional[list[str]]) -> int:
    logger.info("模式: 定时任务")
    logger.info(f"每日执行时间: {config.schedule_time}")

    should_run_immediately = config.schedule_run_immediately
    if getattr(args, "no_run_immediately", False):
        should_run_immediately = False

    logger.info(f"启动时立即执行: {should_run_immediately}")

    from src.scheduler import run_with_schedule

    scheduled_stock_codes = resolve_scheduled_stock_codes(stock_codes)
    schedule_time_provider = build_schedule_time_provider(config.schedule_time)

    def scheduled_task():
        runtime_config = reload_runtime_config()
        run_full_analysis(runtime_config, args, scheduled_stock_codes)

    background_tasks = []
    if getattr(config, "agent_event_monitor_enabled", False):
        from src.agent.events import build_event_monitor_from_config, run_event_monitor_once

        monitor = build_event_monitor_from_config(config)
        if monitor is not None:
            interval_minutes = max(1, getattr(config, "agent_event_monitor_interval_minutes", 5))

            def event_monitor_task():
                triggered = run_event_monitor_once(monitor)
                if triggered:
                    logger.info("[EventMonitor] 本轮触发 %d 条提醒", len(triggered))

            background_tasks.append({
                "task": event_monitor_task,
                "interval_seconds": interval_minutes * 60,
                "run_immediately": True,
                "name": "agent_event_monitor",
            })
        else:
            logger.info("EventMonitor 已启用，但未加载到有效规则，跳过后台提醒任务")

    run_with_schedule(
        task=scheduled_task,
        schedule_time=config.schedule_time,
        run_immediately=should_run_immediately,
        background_tasks=background_tasks,
        schedule_time_provider=schedule_time_provider,
    )
    return 0
