# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 主入口
===================================

职责：解析命令行参数 → 环境引导 → 分发到对应 CLI 模式处理器。

使用方式：
    python main.py              # 正常运行
    python main.py --debug      # 调试模式
    python main.py --dry-run    # 仅获取数据不分析
"""
import argparse
import logging
import os
import sys

from src.config import setup_env

# ── 模块级环境初始化 ──
setup_env()
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    proxy_url = f"http://{os.getenv('PROXY_HOST', '127.0.0.1')}:{os.getenv('PROXY_PORT', '10809')}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url

logger = logging.getLogger(__name__)

# ── 向后兼容：from main import StockAnalysisPipeline ──
from src.core.runner import get_stock_analysis_pipeline  # noqa: E402


class _LazyPipelineDescriptor:
    _resolved = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if self._resolved is None:
            self._resolved = get_stock_analysis_pipeline()
        return self._resolved


class _ModuleExports:
    StockAnalysisPipeline = _LazyPipelineDescriptor()


_exports = _ModuleExports()


def __getattr__(name: str):
    if name == "StockAnalysisPipeline":
        return _exports.StockAnalysisPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── 参数解析 ──


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="A股自选股智能分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                    # 正常运行
  python main.py --debug            # 调试模式
  python main.py --dry-run          # 仅获取数据，不进行 AI 分析
  python main.py --stocks 600519,000001  # 指定分析特定股票
  python main.py --no-notify        # 不发送推送通知
  python main.py --single-notify    # 启用单股推送模式（每分析完一只立即推送）
  python main.py --schedule         # 启用定时任务模式
  python main.py --market-review    # 仅运行大盘复盘
        """,
    )

    parser.add_argument("--debug", action="store_true", help="启用调试模式，输出详细日志")
    parser.add_argument("--dry-run", action="store_true", help="仅获取数据，不进行 AI 分析")
    parser.add_argument("--stocks", type=str, help="指定要分析的股票代码，逗号分隔")
    parser.add_argument("--profile", type=str, default=None, help="使用指定策略画像运行精简分析")
    parser.add_argument("--strategy", type=str, default=None, help="与 --profile 配合使用")
    parser.add_argument("--no-notify", action="store_true", help="不发送推送通知")
    parser.add_argument("--single-notify", action="store_true", help="启用单股推送模式")
    parser.add_argument("--workers", type=int, default=None, help="并发线程数")
    parser.add_argument("--schedule", action="store_true", help="启用定时任务模式")
    parser.add_argument("--no-run-immediately", action="store_true", help="定时任务启动时不立即执行")
    parser.add_argument("--market-review", action="store_true", help="仅运行大盘复盘分析")
    parser.add_argument("--no-market-review", action="store_true", help="跳过大盘复盘分析")
    parser.add_argument("--force-run", action="store_true", help="跳过交易日检查，强制执行")
    parser.add_argument("--webui", action="store_true", help="启动 Web 管理界面")
    parser.add_argument("--webui-only", action="store_true", help="仅启动 Web 服务，不执行分析")
    parser.add_argument("--serve", action="store_true", help="启动 FastAPI 后端服务")
    parser.add_argument("--serve-only", action="store_true", help="仅启动 FastAPI 服务")
    parser.add_argument("--port", type=int, default=8000, help="FastAPI 服务端口")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="FastAPI 监听地址")
    parser.add_argument("--no-context-snapshot", action="store_true", help="不保存分析上下文快照")
    parser.add_argument("--backtest", action="store_true", help="运行回测")
    parser.add_argument("--backtest-code", type=str, default=None, help="仅回测指定股票")
    parser.add_argument("--backtest-days", type=int, default=None, help="回测评估窗口")
    parser.add_argument("--backtest-force", action="store_true", help="强制回测")

    return parser.parse_args()


# ── 主入口 ──


def main() -> int:
    args = parse_arguments()

    from cli import (
        setup_environment,
        parse_stock_codes,
        resolve_webui_args,
        dispatch,
    )

    result = setup_environment(args)
    if isinstance(result, int):
        return result
    config = result

    stock_codes = parse_stock_codes(args)
    resolve_webui_args(args, config)

    return dispatch(config, args, stock_codes)


if __name__ == "__main__":
    sys.exit(main())
