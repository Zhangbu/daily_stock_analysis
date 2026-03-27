# -*- coding: utf-8 -*-
"""
===================================
YfinanceFetcher - 兜底数据源 (Priority 4)
===================================

数据来源：Yahoo Finance（通过 yfinance 库）
特点：国际数据源、可能有延迟或缺失
定位：当所有国内数据源都失败时的最后保障

关键策略：
1. 自动将 A 股代码转换为 yfinance 格式（.SS / .SZ）
2. 处理 Yahoo Finance 的数据格式差异
3. 失败后指数退避重试
"""

import logging
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimiter, STANDARD_COLUMNS
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource, safe_float, safe_int
from .us_index_mapping import get_us_index_yf_symbol, is_us_index_code, is_us_stock_code

logger = logging.getLogger(__name__)


class YfinanceFetcher(BaseFetcher):
    """
    Yahoo Finance 数据源实现
    
    优先级：4（最低，作为兜底）
    数据来源：Yahoo Finance
    
    关键策略：
    - 自动转换股票代码格式
    - 处理时区和数据格式差异
    - 失败后指数退避重试
    - 统一的速率限制（60次/分钟）
    
    注意事项：
    - A 股数据可能有延迟
    - 某些股票可能无数据
    - 数据精度可能与国内源略有差异
    
    Rate Limiting:
    - Default: 60 calls/min, min_interval=1.0s (Yahoo Finance has API limits)
    - Configurable via YFINANCE_RATE_LIMIT and YFINANCE_MIN_INTERVAL env vars
    """
    
    name = "YfinanceFetcher"
    priority = int(os.getenv("YFINANCE_PRIORITY", "4"))
    
    # Rate limiting configuration
    # Yahoo Finance has stricter limits, so we use a conservative default
    DEFAULT_RATE_LIMIT = 60  # calls per minute
    DEFAULT_MIN_INTERVAL = 1.0  # seconds between calls
    
    def __init__(self):
        """
        Initialize YfinanceFetcher with rate limiting.
        
        Rate limit is configurable via environment variables:
        - YFINANCE_RATE_LIMIT: calls per minute (default: 60)
        - YFINANCE_MIN_INTERVAL: minimum seconds between calls (default: 1.0)
        """
        # Initialize rate limiter
        rate_limit = int(os.getenv("YFINANCE_RATE_LIMIT", str(self.DEFAULT_RATE_LIMIT)))
        min_interval = float(os.getenv("YFINANCE_MIN_INTERVAL", str(self.DEFAULT_MIN_INTERVAL)))
        self._rate_limiter = RateLimiter(
            calls_per_minute=rate_limit,
            min_interval=min_interval,
            name="YfinanceFetcher"
        )
        logger.info(
            f"[YfinanceFetcher] Rate limiter initialized: "
            f"{rate_limit} calls/min, min_interval={min_interval}s"
        )
    
    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Yahoo Finance 格式

        Yahoo Finance 代码格式：
        - A股沪市：600519.SS (Shanghai Stock Exchange)
        - A股深市：000001.SZ (Shenzhen Stock Exchange)
        - 港股：0700.HK (Hong Kong Stock Exchange)
        - 美股：AAPL, TSLA, GOOGL (无需后缀)

        Args:
            stock_code: 原始代码，如 '600519', 'hk00700', 'AAPL'

        Returns:
            Yahoo Finance 格式代码

        Examples:
            >>> fetcher._convert_stock_code('600519')
            '600519.SS'
            >>> fetcher._convert_stock_code('hk00700')
            '0700.HK'
            >>> fetcher._convert_stock_code('AAPL')
            'AAPL'
        """
        code = stock_code.strip().upper()

        # 美股指数：映射到 Yahoo Finance 符号（如 SPX -> ^GSPC）
        yf_symbol, _ = get_us_index_yf_symbol(code)
        if yf_symbol:
            logger.debug(f"识别为美股指数: {code} -> {yf_symbol}")
            return yf_symbol

        # 美股：1-5 个大写字母（可选 .X 后缀），原样返回
        if is_us_stock_code(code):
            logger.debug(f"识别为美股代码: {code}")
            return code

        # 港股：hk前缀 -> .HK后缀
        if code.startswith('HK'):
            hk_code = code[2:].lstrip('0') or '0'  # 去除前导0，但保留至少一个0
            hk_code = hk_code.zfill(4)  # 补齐到4位
            logger.debug(f"转换港股代码: {stock_code} -> {hk_code}.HK")
            return f"{hk_code}.HK"

        # 已经包含后缀的情况
        if '.SS' in code or '.SZ' in code or '.HK' in code:
            return code

        # 去除可能的 .SH 后缀
        code = code.replace('.SH', '')

        # ETF: Shanghai ETF (51xx, 52xx, 56xx, 58xx) -> .SS; Shenzhen ETF (15xx, 16xx, 18xx) -> .SZ
        if len(code) == 6:
            if code.startswith(('51', '52', '56', '58')):
                return f"{code}.SS"
            if code.startswith(('15', '16', '18')):
                return f"{code}.SZ"

        # A股：根据代码前缀判断市场
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SS"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            logger.warning(f"无法确定股票 {code} 的市场，默认使用深市")
            return f"{code}.SZ"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从 Yahoo Finance 获取原始数据
        
        使用 yfinance.download() 获取历史数据
        
        流程：
        1. 应用速率限制
        2. 转换股票代码格式
        3. 调用 yfinance API
        4. 处理返回数据
        """
        import yfinance as yf
        
        # Apply rate limiting
        self._rate_limiter.acquire()
        
        # 转换代码格式
        yf_code = self._convert_stock_code(stock_code)
        
        logger.debug(f"调用 yfinance.download({yf_code}, {start_date}, {end_date})")
        
        try:
            # 使用 yfinance 下载数据
            df = yf.download(
                tickers=yf_code,
                start=start_date,
                end=end_date,
                progress=False,  # 禁止进度条
                auto_adjust=True,  # 自动调整价格（复权）
                multi_level_index=True
            )
            
            # 筛选出 yf_code 的列, 避免多只股票数据混淆
            if isinstance(df.columns, pd.MultiIndex) and len(df.columns) > 1:
                ticker_level = df.columns.get_level_values(1)
                mask = ticker_level == yf_code
                if mask.any():
                    df = df.loc[:, mask].copy()
                
            if df.empty:
                raise DataFetchError(f"Yahoo Finance 未查询到 {stock_code} 的数据")
            
            return df
            
        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Yahoo Finance 获取数据失败: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Yahoo Finance 数据
        
        yfinance 返回的列名：
        Open, High, Low, Close, Volume（索引是日期）
        
        注意：新版 yfinance 返回 MultiIndex 列名，如 ('Close', 'AMD')
        需要先扁平化列名再进行处理
        
        需要映射到标准列名：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # 处理 MultiIndex 列名（新版 yfinance 返回格式）
        # 例如: ('Close', 'AMD') -> 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            logger.debug(f"检测到 MultiIndex 列名，进行扁平化处理")
            # 取第一级列名（Price level: Close, High, Low, etc.）
            df.columns = df.columns.get_level_values(0)
        
        # 重置索引，将日期从索引变为列
        df = df.reset_index()
        
        # 列名映射（yfinance 使用首字母大写）
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }
        
        df = df.rename(columns=column_mapping)
        
        # 计算涨跌幅（因为 yfinance 不直接提供）
        if 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)
        
        # 计算成交额（yfinance 不提供，使用估算值）
        # 成交额 ≈ 成交量 * 平均价格
        if 'volume' in df.columns and 'close' in df.columns:
            df['amount'] = df['volume'] * df['close']
        else:
            df['amount'] = 0
        
        # 添加股票代码列
        df['code'] = stock_code
        
        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        
        return df

    def _fetch_yf_ticker_data(self, yf, yf_code: str, name: str, return_code: str) -> Optional[Dict[str, Any]]:
        """
        通过 yfinance 拉取单个指数/股票的行情数据。

        Args:
            yf: yfinance 模块引用
            yf_code: yfinance 使用的代码（如 '000001.SS'、'^GSPC'）
            name: 指数显示名称
            return_code: 写入结果 dict 的 code 字段（如 'sh000001'、'SPX'）

        Returns:
            行情字典，失败时返回 None
        """
        ticker = yf.Ticker(yf_code)
        # 取近两日数据以计算涨跌幅
        hist = ticker.history(period='2d')
        if hist.empty:
            return None
        today_row = hist.iloc[-1]
        prev_row = hist.iloc[-2] if len(hist) > 1 else today_row
        price = float(today_row['Close'])
        prev_close = float(prev_row['Close'])
        change = price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0
        high = float(today_row['High'])
        low = float(today_row['Low'])
        # 振幅 = (最高 - 最低) / 昨收 * 100
        amplitude = ((high - low) / prev_close * 100) if prev_close else 0
        return {
            'code': return_code,
            'name': name,
            'current': price,
            'change': change,
            'change_pct': change_pct,
            'open': float(today_row['Open']),
            'high': high,
            'low': low,
            'prev_close': prev_close,
            'volume': float(today_row['Volume']),
            'amount': 0.0,  # Yahoo Finance 不提供准确成交额
            'amplitude': amplitude,
        }

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        获取主要指数行情 (Yahoo Finance)，支持 A 股与美股。
        region=us 时委托给 _get_us_main_indices。
        """
        import yfinance as yf

        if region == "us":
            return self._get_us_main_indices(yf)

        # A 股指数：akshare 代码 -> (yfinance 代码, 显示名称)
        yf_mapping = {
            'sh000001': ('000001.SS', '上证指数'),
            'sz399001': ('399001.SZ', '深证成指'),
            'sz399006': ('399006.SZ', '创业板指'),
            'sh000688': ('000688.SS', '科创50'),
            'sh000016': ('000016.SS', '上证50'),
            'sh000300': ('000300.SS', '沪深300'),
        }

        results = []
        try:
            for ak_code, (yf_code, name) in yf_mapping.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_code, name, ak_code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] 获取指数 {name} 成功")
                except Exception as e:
                    logger.warning(f"[Yfinance] 获取指数 {name} 失败: {e}")

            if results:
                logger.info(f"[Yfinance] 成功获取 {len(results)} 个 A 股指数行情")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] 获取 A 股指数行情失败: {e}")

        return None

    def _get_us_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """获取美股主要指数行情（SPX、IXIC、DJI、VIX），复用 _fetch_yf_ticker_data"""
        # 大盘复盘所需核心美股指数
        us_indices = ['SPX', 'IXIC', 'DJI', 'VIX']
        results = []
        try:
            for code in us_indices:
                yf_symbol, name = get_us_index_yf_symbol(code)
                if not yf_symbol:
                    continue
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] 获取美股指数 {name} 成功")
                except Exception as e:
                    logger.warning(f"[Yfinance] 获取美股指数 {name} 失败: {e}")

            if results:
                logger.info(f"[Yfinance] 成功获取 {len(results)} 个美股指数行情")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] 获取美股指数行情失败: {e}")

        return None

    def _is_us_stock(self, stock_code: str) -> bool:
        """
        判断代码是否为美股股票（排除美股指数）。

        委托给 us_index_mapping 模块的 is_us_stock_code()。
        """
        return is_us_stock_code(stock_code)

    def _get_us_index_realtime_quote(
        self,
        user_code: str,
        yf_symbol: str,
        index_name: str,
    ) -> Optional[UnifiedRealtimeQuote]:
        """
        Get realtime quote for US index (e.g. SPX -> ^GSPC).

        Args:
            user_code: User input code (e.g. SPX)
            yf_symbol: Yahoo Finance symbol (e.g. ^GSPC)
            index_name: Chinese name for the index

        Returns:
            UnifiedRealtimeQuote or None
        """
        import yfinance as yf

        try:
            logger.debug(f"[Yfinance] 获取美股指数 {user_code} ({yf_symbol}) 实时行情")
            ticker = yf.Ticker(yf_symbol)

            try:
                info = ticker.fast_info
                if info is None:
                    raise ValueError("fast_info is None")
                price = getattr(info, 'lastPrice', None) or getattr(info, 'last_price', None)
                prev_close = getattr(info, 'previousClose', None) or getattr(info, 'previous_close', None)
                open_price = getattr(info, 'open', None)
                high = getattr(info, 'dayHigh', None) or getattr(info, 'day_high', None)
                low = getattr(info, 'dayLow', None) or getattr(info, 'day_low', None)
                volume = getattr(info, 'lastVolume', None) or getattr(info, 'last_volume', None)
            except Exception:
                logger.debug(f"[Yfinance] fast_info 失败，尝试 history 方法")
                hist = ticker.history(period='2d')
                if hist.empty:
                    logger.warning(f"[Yfinance] 无法获取 {yf_symbol} 的数据")
                    return None
                today = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else today
                price = float(today['Close'])
                prev_close = float(prev['Close'])
                open_price = float(today['Open'])
                high = float(today['High'])
                low = float(today['Low'])
                volume = int(today['Volume'])

            change_amount = None
            change_pct = None
            if price is not None and prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100

            amplitude = None
            if high is not None and low is not None and prev_close is not None and prev_close > 0:
                amplitude = ((high - low) / prev_close) * 100

            quote = UnifiedRealtimeQuote(
                code=user_code,
                name=index_name or user_code,
                source=RealtimeSource.FALLBACK,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=None,
                circ_mv=None,
            )
            logger.info(f"[Yfinance] 获取美股指数 {user_code} 实时行情成功: 价格={price}")
            return quote
        except Exception as e:
            logger.warning(f"[Yfinance] 获取美股指数 {user_code} 实时行情失败: {e}")
            return None

    def _extract_fast_info_field(self, info: Any, *field_names: str) -> Any:
        """Read the first non-empty field from yfinance fast_info/info objects."""
        for field_name in field_names:
            try:
                if isinstance(info, dict):
                    value = info.get(field_name)
                else:
                    value = getattr(info, field_name, None)
            except Exception:
                value = None
            if value is not None:
                return value
        return None

    def _build_realtime_quote_from_ticker(
        self,
        *,
        ticker: Any,
        user_code: str,
        default_name: str,
    ) -> Optional[UnifiedRealtimeQuote]:
        """Build a unified realtime quote for US/CN/HK symbols from one ticker."""
        try:
            info = ticker.fast_info
            if info is None:
                raise ValueError("fast_info is None")

            price = safe_float(self._extract_fast_info_field(info, "lastPrice", "last_price"))
            prev_close = safe_float(self._extract_fast_info_field(info, "previousClose", "previous_close"))
            open_price = safe_float(self._extract_fast_info_field(info, "open"))
            high = safe_float(self._extract_fast_info_field(info, "dayHigh", "day_high"))
            low = safe_float(self._extract_fast_info_field(info, "dayLow", "day_low"))
            volume = safe_int(self._extract_fast_info_field(info, "lastVolume", "last_volume", "volume"))
            market_cap = safe_float(self._extract_fast_info_field(info, "marketCap", "market_cap"))
        except Exception:
            logger.debug(f"[Yfinance] fast_info 失败，尝试 history 方法: {user_code}")
            hist = ticker.history(period="2d")
            if hist.empty:
                logger.warning(f"[Yfinance] 无法获取 {user_code} 的数据")
                return None

            today = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else today
            price = safe_float(today.get("Close"))
            prev_close = safe_float(prev.get("Close"))
            open_price = safe_float(today.get("Open"))
            high = safe_float(today.get("High"))
            low = safe_float(today.get("Low"))
            volume = safe_int(today.get("Volume"))
            market_cap = None

        if price is None or price <= 0:
            logger.warning(f"[Yfinance] {user_code} 缺少有效最新价，跳过")
            return None

        change_amount = None
        change_pct = None
        if prev_close is not None and prev_close > 0:
            change_amount = price - prev_close
            change_pct = (change_amount / prev_close) * 100

        amplitude = None
        if high is not None and low is not None and prev_close is not None and prev_close > 0:
            amplitude = ((high - low) / prev_close) * 100

        amount = None
        if volume is not None and price is not None:
            amount = float(volume) * price

        try:
            ticker_info = ticker.info
            name = (
                self._extract_fast_info_field(ticker_info, "shortName", "longName", "displayName")
                or default_name
                or user_code
            )
        except Exception:
            name = default_name or user_code

        return UnifiedRealtimeQuote(
            code=user_code,
            name=name,
            source=RealtimeSource.YFINANCE,
            price=price,
            change_pct=round(change_pct, 2) if change_pct is not None else None,
            change_amount=round(change_amount, 4) if change_amount is not None else None,
            volume=volume,
            amount=round(amount, 2) if amount is not None else None,
            volume_ratio=None,
            turnover_rate=None,
            amplitude=round(amplitude, 2) if amplitude is not None else None,
            open_price=open_price,
            high=high,
            low=low,
            pre_close=prev_close,
            pe_ratio=None,
            pb_ratio=None,
            total_mv=market_cap,
            circ_mv=None,
        )

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        获取美股/美股指数实时行情数据

        支持美股股票（AAPL、TSLA）和美股指数（SPX、DJI 等）。
        数据来源：yfinance Ticker.info

        Args:
            stock_code: 美股代码或指数代码，如 'AMD', 'AAPL', 'SPX', 'DJI'

        Returns:
            UnifiedRealtimeQuote 对象，获取失败返回 None
        """
        import yfinance as yf

        normalized_code = (stock_code or "").strip().upper()

        # 美股指数：使用映射（SPX -> ^GSPC）
        yf_symbol, index_name = get_us_index_yf_symbol(normalized_code)
        if yf_symbol:
            return self._get_us_index_realtime_quote(
                user_code=normalized_code,
                yf_symbol=yf_symbol,
                index_name=index_name,
            )

        try:
            yf_code = self._convert_stock_code(normalized_code)
            logger.debug(f"[Yfinance] 获取实时行情 {normalized_code} -> {yf_code}")
            ticker = yf.Ticker(yf_code)
            quote = self._build_realtime_quote_from_ticker(
                ticker=ticker,
                user_code=normalized_code,
                default_name=normalized_code,
            )
            if quote is not None:
                logger.info(f"[Yfinance] 获取 {normalized_code} 实时行情成功: 价格={quote.price}")
            return quote
        except Exception as e:
            logger.warning(f"[Yfinance] 获取 {stock_code} 实时行情失败: {e}")
            return None

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """Get stock/display name from Yahoo Finance metadata."""
        import yfinance as yf

        normalized_code = (stock_code or "").strip().upper()
        if not normalized_code:
            return None

        try:
            yf_code = self._convert_stock_code(normalized_code)
            ticker = yf.Ticker(yf_code)
            ticker_info = ticker.info
            name = self._extract_fast_info_field(ticker_info, "shortName", "longName", "displayName")
            if isinstance(name, str):
                name = name.strip()
            return name or None
        except Exception as e:
            logger.debug(f"[Yfinance] 获取股票名称失败 {stock_code}: {e}")
            return None


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = YfinanceFetcher()
    
    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"获取失败: {e}")
