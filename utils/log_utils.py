# -*- coding: utf-8 -*-
"""
===================================
Structured Logging Utilities
===================================

Provides structured logging with dimensions for stocks, strategies,
and operations. Enables better log filtering and analysis.

Features:
1. Stock-dimension logging (stock code tracking)
2. Strategy-dimension logging (strategy name tracking)
3. Operation-dimension logging (cache, backtest, etc.)
4. Source tracking (data source identification)
5. Unified logging format

Usage:
    from utils.log_utils import StructuredLogger
    
    # Stock logging
    StructuredLogger.stock_info("600519", "Data fetched successfully", source="Akshare")
    StructuredLogger.stock_error("600519", "Failed to fetch data", source="Akshare")
    
    # Strategy logging
    StructuredLogger.strategy_info("MA金叉", "Strategy matched")
    
    # Backtest logging
    StructuredLogger.backtest_info("600519", "MA金叉", "Win rate: 65%")
    
    # Cache logging
    StructuredLogger.cache_info("600519", "READ", "Cache hit")
"""

import logging
from typing import Optional

# Get the root logger
logger = logging.getLogger(__name__)


def build_log_context(**fields: object) -> str:
    """Build a compact log context string from non-empty fields."""
    parts = []
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return f"[{' '.join(parts)}]" if parts else ""


class StructuredLogger:
    """
    Structured logging utilities with dimension support.
    
    This class provides convenience methods for logging with
    additional context dimensions (stock, strategy, operation, source)
    that can be used for filtering and analysis.
    """
    
    # ==================== Stock Logging ====================
    
    @staticmethod
    def stock_info(stock_code: str, message: str, source: str = "SYSTEM") -> None:
        """
        Log stock-related information.
        
        Args:
            stock_code: Stock code (e.g., "600519")
            message: Log message
            source: Data source name (e.g., "Akshare", "Efinance")
        """
        logger.info(
            f"[{stock_code}] {message}",
            extra={'stock': stock_code, 'source': source}
        )
    
    @staticmethod
    def stock_warning(stock_code: str, message: str, source: str = "SYSTEM") -> None:
        """
        Log stock-related warning.
        
        Args:
            stock_code: Stock code
            message: Warning message
            source: Data source name
        """
        logger.warning(
            f"[{stock_code}] {message}",
            extra={'stock': stock_code, 'source': source}
        )
    
    @staticmethod
    def stock_error(stock_code: str, message: str, source: str = "SYSTEM") -> None:
        """
        Log stock-related error.
        
        Args:
            stock_code: Stock code
            message: Error message
            source: Data source name
        """
        logger.error(
            f"[{stock_code}] {message}",
            extra={'stock': stock_code, 'source': source}
        )
    
    @staticmethod
    def stock_debug(stock_code: str, message: str, source: str = "SYSTEM") -> None:
        """
        Log stock-related debug information.
        
        Args:
            stock_code: Stock code
            message: Debug message
            source: Data source name
        """
        logger.debug(
            f"[{stock_code}] {message}",
            extra={'stock': stock_code, 'source': source}
        )
    
    # ==================== Strategy Logging ====================
    
    @staticmethod
    def strategy_info(strategy_name: str, message: str) -> None:
        """
        Log strategy-related information.
        
        Args:
            strategy_name: Strategy name (e.g., "MA金叉", "底部放量")
            message: Log message
        """
        logger.info(
            f"[策略:{strategy_name}] {message}",
            extra={'strategy': strategy_name}
        )
    
    @staticmethod
    def strategy_warning(strategy_name: str, message: str) -> None:
        """
        Log strategy-related warning.
        
        Args:
            strategy_name: Strategy name
            message: Warning message
        """
        logger.warning(
            f"[策略:{strategy_name}] {message}",
            extra={'strategy': strategy_name}
        )
    
    @staticmethod
    def strategy_error(strategy_name: str, message: str) -> None:
        """
        Log strategy-related error.
        
        Args:
            strategy_name: Strategy name
            message: Error message
        """
        logger.error(
            f"[策略:{strategy_name}] {message}",
            extra={'strategy': strategy_name}
        )
    
    # ==================== Backtest Logging ====================
    
    @staticmethod
    def backtest_info(stock_code: str, strategy_name: str, message: str) -> None:
        """
        Log backtest-related information.
        
        Args:
            stock_code: Stock code
            strategy_name: Strategy name
            message: Log message
        """
        logger.info(
            f"[回测] {stock_code} - {strategy_name}: {message}",
            extra={
                'stock': stock_code,
                'strategy': strategy_name,
                'type': 'backtest'
            }
        )
    
    @staticmethod
    def backtest_result(stock_code: str, strategy_name: str, result: dict) -> None:
        """
        Log backtest result summary.
        
        Args:
            stock_code: Stock code
            strategy_name: Strategy name
            result: Backtest result dictionary
        """
        message = (
            f"Trades={result.get('total_trades', 0)}, "
            f"WinRate={result.get('win_rate', 0):.2%}, "
            f"Return={result.get('total_profit_pct', 0):.2f}%"
        )
        StructuredLogger.backtest_info(stock_code, strategy_name, message)
    
    # ==================== Cache Logging ====================
    
    @staticmethod
    def cache_info(stock_code: str, operation: str, message: str) -> None:
        """
        Log cache operation.
        
        Args:
            stock_code: Stock code
            operation: Operation type (READ, WRITE, CLEAR, HIT, MISS)
            message: Log message
        """
        logger.debug(
            f"[缓存] {operation} - {stock_code}: {message}",
            extra={'stock': stock_code, 'operation': operation, 'type': 'cache'}
        )
    
    @staticmethod
    def cache_hit(stock_code: str, date_range: str) -> None:
        """Log cache hit."""
        StructuredLogger.cache_info(stock_code, "HIT", f"Cache hit for {date_range}")
    
    @staticmethod
    def cache_miss(stock_code: str, reason: str) -> None:
        """Log cache miss."""
        StructuredLogger.cache_info(stock_code, "MISS", f"Cache miss: {reason}")
    
    @staticmethod
    def cache_write(stock_code: str, rows: int) -> None:
        """Log cache write."""
        StructuredLogger.cache_info(stock_code, "WRITE", f"Wrote {rows} rows to cache")
    
    @staticmethod
    def cache_clear(stock_code: Optional[str] = None) -> None:
        """Log cache clear."""
        if stock_code:
            StructuredLogger.cache_info(stock_code, "CLEAR", "Cache cleared")
        else:
            logger.info("[缓存] All cache cleared", extra={'operation': 'CLEAR', 'type': 'cache'})
    
    # ==================== Data Fetcher Logging ====================
    
    @staticmethod
    def fetcher_start(fetcher_name: str, stock_code: str) -> None:
        """Log data fetcher start."""
        logger.info(
            f"[{fetcher_name}] Fetching data for {stock_code}...",
            extra={'source': fetcher_name, 'stock': stock_code}
        )
    
    @staticmethod
    def fetcher_success(fetcher_name: str, stock_code: str, rows: int) -> None:
        """Log data fetcher success."""
        logger.info(
            f"[{fetcher_name}] Successfully fetched {rows} rows for {stock_code}",
            extra={'source': fetcher_name, 'stock': stock_code}
        )
    
    @staticmethod
    def fetcher_error(fetcher_name: str, stock_code: str, error: str) -> None:
        """Log data fetcher error."""
        logger.error(
            f"[{fetcher_name}] Error fetching {stock_code}: {error}",
            extra={'source': fetcher_name, 'stock': stock_code}
        )
    
    @staticmethod
    def fetcher_fallback(original: str, fallback: str, stock_code: str) -> None:
        """Log data fetcher fallback."""
        logger.warning(
            f"[{original}] Failed for {stock_code}, falling back to {fallback}",
            extra={'source': fallback, 'stock': stock_code, 'fallback_from': original}
        )
    
    # ==================== Batch Operation Logging ====================
    
    @staticmethod
    def batch_start(operation: str, total: int) -> None:
        """Log batch operation start."""
        logger.info(
            f"[批量] {operation}: Started, total={total}",
            extra={'operation': operation, 'total': total}
        )
    
    @staticmethod
    def batch_progress(operation: str, completed: int, total: int) -> None:
        """Log batch operation progress."""
        logger.debug(
            f"[批量] {operation}: Progress {completed}/{total} ({completed/total:.1%})",
            extra={'operation': operation, 'completed': completed, 'total': total}
        )
    
    @staticmethod
    def batch_complete(operation: str, total: int, success: int, failed: int) -> None:
        """Log batch operation completion."""
        logger.info(
            f"[批量] {operation}: Complete, success={success}, failed={failed}, total={total}",
            extra={'operation': operation, 'success': success, 'failed': failed, 'total': total}
        )
    
    # ==================== Analysis Logging ====================
    
    @staticmethod
    def analysis_start(stock_code: str) -> None:
        """Log analysis start."""
        logger.info(
            f"[分析] Starting analysis for {stock_code}",
            extra={'stock': stock_code, 'type': 'analysis'}
        )
    
    @staticmethod
    def analysis_complete(stock_code: str, duration: float) -> None:
        """Log analysis completion."""
        logger.info(
            f"[分析] Completed analysis for {stock_code} in {duration:.2f}s",
            extra={'stock': stock_code, 'type': 'analysis', 'duration': duration}
        )
    
    @staticmethod
    def analysis_error(stock_code: str, error: str) -> None:
        """Log analysis error."""
        logger.error(
            f"[分析] Analysis failed for {stock_code}: {error}",
            extra={'stock': stock_code, 'type': 'analysis'}
        )
    
    # ==================== General Logging ====================
    
    @staticmethod
    def system_info(message: str) -> None:
        """Log system-level information."""
        logger.info(f"[系统] {message}", extra={'type': 'system'})
    
    @staticmethod
    def system_warning(message: str) -> None:
        """Log system-level warning."""
        logger.warning(f"[系统] {message}", extra={'type': 'system'})
    
    @staticmethod
    def system_error(message: str) -> None:
        """Log system-level error."""
        logger.error(f"[系统] {message}", extra={'type': 'system'})


class LogContext:
    """
    Context manager for adding consistent log context.
    
    Usage:
        with LogContext(stock="600519", source="Akshare"):
            StructuredLogger.stock_info("Data fetched successfully")
    """
    
    def __init__(self, **kwargs):
        """
        Initialize log context.
        
        Args:
            **kwargs: Key-value pairs to add to log context
        """
        self.context = kwargs
    
    def __enter__(self):
        """Enter context and add extra fields."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        return False


def setup_structured_logging_formatter(formatter: logging.Formatter) -> None:
    """
    Setup logging formatter to support structured fields.
    
    This function can be used to customize the log format
    to include structured fields like [stock], [strategy], etc.
    
    Args:
        formatter: Logging formatter to configure
    """
    # The formatter already supports extra fields through %()s syntax
    # This function is a placeholder for future enhancements
    pass
