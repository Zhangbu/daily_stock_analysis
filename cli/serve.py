# -*- coding: utf-8 -*-
"""
===================================
CLI 模式: Web 服务启动
===================================
"""
import logging
import os
import threading

from src.config import Config
from src.webui_frontend import prepare_webui_frontend_assets

logger = logging.getLogger(__name__)


def start_api_server(host: str, port: int, config: Config) -> None:
    import uvicorn

    def run_server():
        level_name = (config.log_level or "INFO").lower()
        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            log_level=level_name,
            log_config=None,
        )

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info(f"FastAPI 服务已启动: http://{host}:{port}")


def start_bot_stream_clients(config: Config) -> None:
    """Start bot stream clients when enabled in config."""
    if config.dingtalk_stream_enabled:
        try:
            from bot.platforms import start_dingtalk_stream_background, DINGTALK_STREAM_AVAILABLE

            if DINGTALK_STREAM_AVAILABLE:
                if start_dingtalk_stream_background():
                    logger.info("[Main] Dingtalk Stream client started in background.")
                else:
                    logger.warning("[Main] Dingtalk Stream client failed to start.")
            else:
                logger.warning("[Main] Dingtalk Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install dingtalk-stream")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Dingtalk Stream client: {exc}")

    if getattr(config, "feishu_stream_enabled", False):
        try:
            from bot.platforms import start_feishu_stream_background, FEISHU_SDK_AVAILABLE

            if FEISHU_SDK_AVAILABLE:
                if start_feishu_stream_background():
                    logger.info("[Main] Feishu Stream client started in background.")
                else:
                    logger.warning("[Main] Feishu Stream client failed to start.")
            else:
                logger.warning("[Main] Feishu Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install lark-oapi")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Feishu Stream client: {exc}")


def handle_serve(args, config: Config) -> bool:
    """Start web server and bot clients. Returns True if bot clients started."""
    if not prepare_webui_frontend_assets():
        logger.warning("前端静态资源未就绪，继续启动 FastAPI 服务（Web 页面可能不可用）")

    bot_clients_started = False
    try:
        start_api_server(host=args.host, port=args.port, config=config)
        bot_clients_started = True
    except Exception as e:
        logger.error(f"启动 FastAPI 服务失败: {e}")

    if bot_clients_started:
        start_bot_stream_clients(config)

    return bot_clients_started
