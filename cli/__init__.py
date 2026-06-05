# -*- coding: utf-8 -*-
"""
===================================
CLI 调度器 — 共享引导与模式分发
===================================
"""
import logging
import os
import sys

from data_provider.base import canonical_stock_code
from src.config import get_config
from src.logging_config import setup_logging
from src.webui_frontend import prepare_webui_frontend_assets

logger = logging.getLogger(__name__)


def setup_environment(args):
    """Bootstrap config + logging, return Config on success or exit code (int) on failure."""
    from src.core.runner import bootstrap_environment, setup_bootstrap_logging

    bootstrap_environment()

    try:
        setup_bootstrap_logging(debug=args.debug)
    except Exception as exc:
        logging.basicConfig(
            level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        logger.warning("Bootstrap 日志初始化失败，已回退到 stderr: %s", exc)

    try:
        config = get_config()
    except Exception as exc:
        logger.exception("加载配置失败: %s", exc)
        return 1

    try:
        setup_logging(log_prefix="stock_analysis", debug=args.debug, log_dir=config.log_dir)
    except Exception as exc:
        logger.exception("切换到配置日志目录失败: %s", exc)
        return 1

    logger.info("=" * 60)
    logger.info("A股自选股智能分析系统 启动")
    logger.info("=" * 60)

    warnings = config.validate()
    for w in warnings:
        logger.warning(w)

    return config


def parse_stock_codes(args) -> list[str] | None:
    """Parse --stocks argument into a list of canonical stock codes."""
    if not args.stocks:
        return None
    codes = [
        canonical_stock_code(c)
        for c in args.stocks.split(",")
        if (c or "").strip()
    ]
    logger.info("使用命令行指定的股票列表: %s", codes)
    return codes


def resolve_webui_args(args, config):
    """Normalise --webui / --webui-only to --serve / --serve-only."""
    if args.webui:
        args.serve = True
    if args.webui_only:
        args.serve_only = True
    if config.webui_enabled and not (args.serve or args.serve_only):
        args.serve = True


def should_start_serve(args) -> bool:
    return (args.serve or args.serve_only) and os.getenv("GITHUB_ACTIONS") != "true"


def apply_legacy_webui_host_port(args):
    """Backward compat: WEBUI_HOST / WEBUI_PORT env vars."""
    if args.host == "0.0.0.0" and os.getenv("WEBUI_HOST"):
        args.host = os.getenv("WEBUI_HOST")
    if args.port == 8000 and os.getenv("WEBUI_PORT"):
        args.port = int(os.getenv("WEBUI_PORT"))


def dispatch(config, args, stock_codes):
    """Route to the appropriate mode handler."""
    from cli.serve import handle_serve
    from cli.backtest import handle_backtest
    from cli.profile import handle_profile
    from cli.market_review import handle_market_review
    from cli.schedule import handle_schedule
    from cli.analyze import handle_analyze

    # ── Serve mode ──
    start_serve = should_start_serve(args)
    if start_serve:
        apply_legacy_webui_host_port(args)
        bot_started = handle_serve(args, config)
    else:
        bot_started = False

    if args.serve_only:
        logger.info("模式: 仅 Web 服务")
        logger.info(f"Web 服务运行中: http://{args.host}:{args.port}")
        logger.info("通过 /api/v1/analysis/analyze 接口触发分析")
        logger.info(f"API 文档: http://{args.host}:{args.port}/docs")
        logger.info("按 Ctrl+C 退出...")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n用户中断，程序退出")
        return 0

    try:
        # ── Backtest mode ──
        if getattr(args, "backtest", False):
            return handle_backtest(args)

        # ── Profile strategy mode ──
        if getattr(args, "profile", None):
            return handle_profile(args, stock_codes)

        # ── Market review only mode ──
        if args.market_review:
            return handle_market_review(args, config)

        # ── Schedule mode ──
        if args.schedule or config.schedule_enabled:
            return handle_schedule(args, config, stock_codes)

        # ── Normal single run ──
        return handle_analyze(args, config, stock_codes, start_serve)

    except KeyboardInterrupt:
        logger.info("\n用户中断，程序退出")
        return 130
    except Exception as e:
        logger.exception(f"程序执行失败: {e}")
        return 1
