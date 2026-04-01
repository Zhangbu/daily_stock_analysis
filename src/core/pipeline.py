# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 核心分析流水线
===================================

职责：
1. 管理整个分析流程
2. 协调数据获取、存储、搜索、分析、通知等模块
3. 实现并发控制和异常处理
4. 提供股票分析的核心功能
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

from src.config import get_config, Config
from src.storage import get_db
from data_provider import DataFetcherManager
from data_provider.realtime_types import ChipDistribution
from src.analyzer import GeminiAnalyzer, AnalysisResult, STOCK_NAME_MAP
from src.notification import NotificationService
from src.search_service import SearchService
from src.enums import ReportType
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult
from src.core.analysis_delivery import AnalysisDeliveryService
from src.core.analysis_engine_router import AnalysisEngineRouter
from src.core.analysis_inputs import ParallelAnalysisInputCollector
from src.core.analysis_persistence import AnalysisPersistenceService
from src.core.intel_coordinator import IntelCoordinator
from src.core.analysis_quality import AnalysisQualityGuard, StageLatencyRecorder
from src.core.trading_calendar import get_market_for_stock, is_market_open
from bot.models import BotMessage
from utils.log_utils import build_log_context
from utils.observability import OperationTimer


logger = logging.getLogger(__name__)


class StockAnalysisPipeline:
    """
    股票分析主流程调度器
    
    职责：
    1. 管理整个分析流程
    2. 协调数据获取、存储、搜索、分析、通知等模块
    3. 实现并发控制和异常处理
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        max_workers: Optional[int] = None,
        source_message: Optional[BotMessage] = None,
        query_id: Optional[str] = None,
        query_source: Optional[str] = None,
        save_context_snapshot: Optional[bool] = None
    ):
        """
        初始化调度器
        
        Args:
            config: 配置对象（可选，默认使用全局配置）
            max_workers: 最大并发线程数（可选，默认从配置读取）
        """
        self.config = config or get_config()
        self.max_workers = max_workers or self.config.max_workers
        self.source_message = source_message
        self.query_id = query_id
        self.query_source = self._resolve_query_source(query_source)
        self.save_context_snapshot = (
            self.config.save_context_snapshot if save_context_snapshot is None else save_context_snapshot
        )
        
        # 初始化各模块
        self.db = get_db()
        self.persistence = AnalysisPersistenceService(
            db=self.db,
            save_context_snapshot=self.save_context_snapshot,
            safe_to_dict=self._safe_to_dict,
        )
        self.fetcher_manager = DataFetcherManager()
        # 不再单独创建 akshare_fetcher，统一使用 fetcher_manager 获取增强数据
        self.trend_analyzer = StockTrendAnalyzer()  # 趋势分析器
        self.analyzer = GeminiAnalyzer()
        self.notifier = NotificationService(source_message=source_message)
        self.delivery_service = AnalysisDeliveryService(notifier=self.notifier, config=self.config)
        self.engine_router = AnalysisEngineRouter(config=self.config)
        
        # 初始化搜索服务
        self.search_service = SearchService(
            bocha_keys=self.config.bocha_api_keys,
            tavily_keys=self.config.tavily_api_keys,
            brave_keys=self.config.brave_api_keys,
            serpapi_keys=self.config.serpapi_keys,
            news_max_age_days=self.config.news_max_age_days,
        )
        self.intel_coordinator = IntelCoordinator(
            search_service=self.search_service,
            persistence=self.persistence,
            build_query_context=self._build_query_context,
        )
        self.input_collector = ParallelAnalysisInputCollector(logger=logger)
        self.quality_guard = AnalysisQualityGuard(config=self.config, logger=logger)
        self.stage_latency_recorder = StageLatencyRecorder(logger=logger)
        
        init_context = build_log_context(query_id=self.query_id, query_source=self.query_source)
        logger.info(f"{init_context} 调度器初始化完成，最大并发数: {self.max_workers}")
        logger.info("已启用趋势分析器 (MA5>MA10>MA20 多头判断)")
        # 打印实时行情/筹码配置状态
        if self.config.enable_realtime_quote:
            logger.info(f"实时行情已启用 (优先级: {self.config.realtime_source_priority})")
        else:
            logger.info("实时行情已禁用，将使用历史收盘价")
        if self.config.enable_chip_distribution:
            logger.info("筹码分布分析已启用")
        else:
            logger.info("筹码分布分析已禁用")
        if self.search_service.is_available:
            logger.info("搜索服务已启用 (Tavily/SerpAPI)")
        else:
            logger.warning("搜索服务未启用（未配置 API Key）")
    
    def fetch_and_save_stock_data(
        self, 
        code: str,
        force_refresh: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        获取并保存单只股票数据
        
        断点续传逻辑：
        1. 检查数据库是否已有今日数据
        2. 如果有且不强制刷新，则跳过网络请求
        3. 否则从数据源获取并保存
        
        Args:
            code: 股票代码
            force_refresh: 是否强制刷新（忽略本地缓存）
            
        Returns:
            Tuple[是否成功, 错误信息]
        """
        with OperationTimer(
            logger,
            "fetch_and_save_stock_data",
            query_id=self.query_id,
            stock_code=code,
            query_source=self.query_source,
        ) as timer:
            try:
                today = date.today()

                # 断点续传检查：如果今日数据已存在，跳过
                if not force_refresh and self.persistence.has_today_data(code, today):
                    timer.update(cache_hit=True, provider="database")
                    timer.set_message("今日数据已存在，跳过获取（断点续传）")
                    context = build_log_context(query_id=self.query_id, stock_code=code, query_source=self.query_source, cache_hit=True)
                    logger.info(f"{context} 今日数据已存在，跳过获取（断点续传）")
                    return True, None

                # 从数据源获取数据（使用配置的扩展时间范围）
                historical_days = self.config.historical_data_days
                timer.update(cache_hit=False)
                context = build_log_context(query_id=self.query_id, stock_code=code, query_source=self.query_source, cache_hit=False)
                logger.info(f"{context} 开始从数据源获取数据（{historical_days}天）...")
                df, source_name = self.fetcher_manager.get_daily_data(code, days=historical_days)

                if df is None or df.empty:
                    timer.mark_failed("获取数据为空")
                    timer.set_message("获取数据为空")
                    return False, "获取数据为空"

                # 保存到数据库
                saved_count = self.persistence.save_daily_data(df, code, source_name)
                timer.update(provider=source_name)
                timer.set_message(f"saved_rows={saved_count}")
                success_context = build_log_context(
                    query_id=self.query_id,
                    stock_code=code,
                    query_source=self.query_source,
                    provider=source_name,
                )
                logger.info(f"{success_context} 数据保存成功（新增 {saved_count} 条）")

                return True, None

            except Exception as e:
                error_msg = f"获取/保存数据失败: {str(e)}"
                timer.mark_failed(error_msg)
                timer.set_message(error_msg)
                error_context = build_log_context(query_id=self.query_id, stock_code=code, query_source=self.query_source)
                logger.error(f"{error_context} {error_msg}")
                return False, error_msg
    
    def analyze_stock(self, code: str, report_type: ReportType, query_id: str) -> Optional[AnalysisResult]:
        """
        分析单只股票（增强版：含量比、换手率、筹码分析、多维度情报）
        
        流程：
        1. 获取实时行情（量比、换手率）- 通过 DataFetcherManager 自动故障切换
        2. 获取筹码分布 - 通过 DataFetcherManager 带熔断保护
        3. 进行趋势分析（基于交易理念）
        4. 多维度情报搜索（最新消息+风险排查+业绩预期）
        5. 从数据库获取分析上下文
        6. 调用 AI 进行综合分析
        
        Args:
            query_id: 查询链路关联 id
            code: 股票代码
            report_type: 报告类型
            
        Returns:
            AnalysisResult 或 None（如果分析失败）
        """
        with OperationTimer(
            logger,
            "analyze_stock",
            query_id=query_id,
            stock_code=code,
            query_source=self.query_source,
        ) as timer:
            try:
                # 获取股票名称（优先从实时行情获取真实名称）
                stock_name = STOCK_NAME_MAP.get(code, '')

                # Step 1 & 2: 并行获取所有增强数据
                realtime_quote, chip_data, flow_data, dragon_tiger_data, sector_data = self._fetch_enhanced_market_data(code)

                if realtime_quote:
                    if realtime_quote.name:
                        stock_name = realtime_quote.name
                    volume_ratio = getattr(realtime_quote, 'volume_ratio', None)
                    turnover_rate = getattr(realtime_quote, 'turnover_rate', None)
                    logger.info(
                        f"[{code}] {stock_name} 实时行情: 价格={realtime_quote.price}, "
                        f"量比={volume_ratio}, 换手率={turnover_rate}% "
                        f"(来源: {realtime_quote.source.value if hasattr(realtime_quote, 'source') else 'unknown'})"
                    )
                else:
                    logger.info(f"[{code}] 实时行情获取失败或已禁用，将使用历史数据进行分析")

                if chip_data:
                    logger.info(
                        f"[{code}] 筹码分布: 获利比例={chip_data.profit_ratio:.1%}, "
                        f"90%集中度={chip_data.concentration_90:.2%}"
                    )
                else:
                    logger.debug(f"[{code}] 筹码分布获取失败或已禁用")

                if not stock_name:
                    stock_name = f'股票{code}'

                result = self.engine_router.route(
                    code=code,
                    run_agent=lambda: self._analyze_with_agent(
                        code,
                        report_type,
                        query_id,
                        stock_name,
                        realtime_quote,
                        chip_data,
                        flow_data,
                        dragon_tiger_data,
                        sector_data,
                    ),
                    run_standard=lambda: self._analyze_with_standard_engine(
                        code,
                        report_type,
                        query_id,
                        stock_name,
                        realtime_quote,
                        chip_data,
                        flow_data,
                        dragon_tiger_data,
                        sector_data,
                    ),
                )
                timer.set_message(f"success={bool(result)}")
                return result

            except Exception as e:
                timer.mark_failed(str(e))
                timer.set_message(str(e))
                logger.error(f"[{code}] 分析失败: {e}")
                logger.exception(f"[{code}] 详细错误信息:")
                return None

    def _fetch_enhanced_market_data(self, code: str) -> Tuple[Any, Optional[ChipDistribution], Optional[Any], Optional[Any], Optional[Dict]]:
        """
        Fetch realtime quote, chip distribution, fund flow, dragon tiger, and sector rotation concurrently.
        """
        realtime_quote = None
        chip_data = None
        flow_data = None
        dragon_tiger_data = None
        sector_data = None
        tasks = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            if self.config.enable_realtime_quote:
                tasks["realtime_quote"] = executor.submit(self.fetcher_manager.get_realtime_quote, code)
            if getattr(self.config, 'enable_chip_distribution', True):
                tasks["chip_distribution"] = executor.submit(self.fetcher_manager.get_chip_distribution, code)
            if getattr(self.config, 'enable_fund_flow', True):
                tasks["fund_flow"] = executor.submit(self.fetcher_manager.get_fund_flow, code)
            if getattr(self.config, 'enable_dragon_tiger', True):
                tasks["dragon_tiger"] = executor.submit(self.fetcher_manager.get_dragon_tiger, code)
            if getattr(self.config, 'enable_sector_rotation', True):
                tasks["sector_rotation"] = executor.submit(self.fetcher_manager.get_stock_sector_rotation, code)

            for task_name, future in tasks.items():
                try:
                    value = future.result()
                    if task_name == "realtime_quote":
                        realtime_quote = value
                    elif task_name == "chip_distribution":
                        chip_data = value
                    elif task_name == "fund_flow":
                        flow_data = value
                    elif task_name == "dragon_tiger":
                        dragon_tiger_data = value
                    elif task_name == "sector_rotation":
                        sector_data = value
                except Exception as exc:
                    logger.warning(f"[{code}] 获取 {task_name} 数据失败: {exc}")

        return realtime_quote, chip_data, flow_data, dragon_tiger_data, sector_data

    def _analyze_with_standard_engine(
        self,
        code: str,
        report_type: ReportType,
        query_id: str,
        stock_name: str,
        realtime_quote: Any,
        chip_data: Optional[ChipDistribution],
        flow_data: Optional[Any] = None,
        dragon_tiger_data: Optional[Any] = None,
        sector_data: Optional[Dict] = None,
    ) -> Optional[AnalysisResult]:
        """Run the standard analysis engine using local pipeline dependencies."""
        try:
            stage_started_at = time.perf_counter()
            trend_result, news_context = self._collect_parallel_analysis_inputs(
                code=code,
                stock_name=stock_name,
                query_id=query_id,
                realtime_quote=realtime_quote,
            )
            self._log_stage_latency(code=code, stage_name="inputs_parallel", started_at=stage_started_at)

            # Step 5: 获取分析上下文（技术面数据）
            context = self.persistence.get_analysis_context(code)
            
            if context is None:
                logger.warning(f"[{code}] 无法获取历史行情数据，将仅基于新闻和实时行情分析")
                context = {
                    'code': code,
                    'stock_name': stock_name,
                    'date': date.today().isoformat(),
                    'data_missing': True,
                    'today': {},
                    'yesterday': {}
                }
            
            # Step 6: 增强上下文数据（添加实时行情、筹码、趋势分析结果、股票名称、资金流、龙虎榜、板块）
            enhanced_context = self._enhance_context(
                context, 
                realtime_quote, 
                chip_data, 
                trend_result,
                stock_name,  # 传入股票名称
                flow_data,
                dragon_tiger_data,
                sector_data
            )
            
            # Step 7: 调用 AI 分析（传入增强的上下文和新闻）
            llm_started_at = time.perf_counter()
            result = self.analyzer.analyze(enhanced_context, news_context=news_context)
            self._log_stage_latency(code=code, stage_name="llm_analyze", started_at=llm_started_at)

            # Step 7.5: 填充分析时的价格信息到 result
            if result:
                realtime_data = enhanced_context.get('realtime', {})
                result.current_price = realtime_data.get('price')
                result.change_pct = realtime_data.get('change_pct')
                # Reuse already loaded context date in stale-data guard to avoid extra DB lookup.
                result.context_date_hint = enhanced_context.get("date") or context.get("date")
                self._apply_data_completeness_guard(
                    result=result,
                    code=code,
                    context=enhanced_context,
                    trend_result=trend_result,
                    news_context=news_context,
                    realtime_quote=realtime_quote,
                )

            # Step 8: 保存分析历史记录
            if result:
                try:
                    context_snapshot = self.persistence.build_context_snapshot(
                        enhanced_context=enhanced_context,
                        news_content=news_context,
                        realtime_quote=realtime_quote,
                        chip_data=chip_data
                    )
                    if flow_data:
                        # Append flow data generically to the saved snapshot
                        context_snapshot['fund_flow'] = flow_data.to_dict()
                    if dragon_tiger_data:
                        context_snapshot['dragon_tiger'] = dragon_tiger_data.to_dict() if hasattr(dragon_tiger_data, 'to_dict') else dragon_tiger_data
                    if sector_data:
                        context_snapshot['sector_rotation'] = sector_data
                        
                    self.persistence.save_analysis_history(
                        result=result,
                        query_id=query_id,
                        report_type=report_type.value,
                        news_content=news_context,
                        context_snapshot=context_snapshot,
                    )
                except Exception as e:
                    logger.warning(f"[{code}] 保存分析历史失败: {e}")

            return result

        except Exception as e:
            logger.error(f"[{code}] 标准分析失败: {e}")
            logger.exception(f"[{code}] 标准分析详细错误信息:")
            return None

    def _log_stage_latency(self, *, code: str, stage_name: str, started_at: float) -> None:
        """Log stage latency for pipeline bottleneck diagnosis."""
        self._get_stage_latency_recorder().log(
            code=code,
            stage_name=stage_name,
            started_at=started_at,
        )

    def _get_stage_latency_recorder(self) -> StageLatencyRecorder:
        """Return stage latency recorder, creating a fallback instance for tests."""
        recorder = getattr(self, "stage_latency_recorder", None)
        if recorder is None:
            recorder = StageLatencyRecorder(logger=logger)
            self.stage_latency_recorder = recorder
        return recorder

    def _collect_parallel_analysis_inputs(
        self,
        *,
        code: str,
        stock_name: str,
        query_id: str,
        realtime_quote: Any,
    ) -> Tuple[Optional[TrendAnalysisResult], str]:
        """Collect trend and intel inputs concurrently to reduce critical path latency."""
        return self._get_input_collector().collect(
            code=code,
            trend_task=lambda: self._build_trend_result(code=code, realtime_quote=realtime_quote),
            intel_task=lambda: self.intel_coordinator.collect_comprehensive_intel(
                code=code,
                stock_name=stock_name,
                query_id=query_id,
                max_searches=5,
            ),
            log_stage_latency=lambda stage, started_at: self._log_stage_latency(
                code=code,
                stage_name=stage,
                started_at=started_at,
            ),
        )

    def _get_input_collector(self) -> ParallelAnalysisInputCollector:
        """Return input collector, creating a fallback instance for tests."""
        collector = getattr(self, "input_collector", None)
        if collector is None:
            collector = ParallelAnalysisInputCollector(logger=logger)
            self.input_collector = collector
        return collector

    def _build_trend_result(
        self,
        *,
        code: str,
        realtime_quote: Any,
    ) -> Optional[TrendAnalysisResult]:
        """Build trend analysis result from historical bars and optional realtime quote."""
        end_date = date.today()
        start_date = end_date - timedelta(days=89)
        historical_bars = self.persistence.get_data_range(code, start_date, end_date)
        if not historical_bars:
            return None

        df = pd.DataFrame([bar.to_dict() for bar in historical_bars])
        if self.config.enable_realtime_quote and realtime_quote:
            df = self._augment_historical_with_realtime(df, realtime_quote, code)
        trend_result = self.trend_analyzer.analyze(df, code)
        logger.info(
            f"[{code}] 趋势分析: {trend_result.trend_status.value}, "
            f"买入信号={trend_result.buy_signal.value}, 评分={trend_result.signal_score}"
        )
        return trend_result

    def _apply_data_completeness_guard(
        self,
        *,
        result: AnalysisResult,
        code: str,
        context: Dict[str, Any],
        trend_result: Optional[TrendAnalysisResult],
        news_context: str,
        realtime_quote: Any,
    ) -> None:
        """Downgrade confidence when key data dimensions are missing."""
        self._get_quality_guard().apply_data_completeness_guard(
            result=result,
            code=code,
            context=context,
            trend_result=trend_result,
            news_context=news_context,
            realtime_quote=realtime_quote,
        )

    def _enhance_context(
        self,
        context: Dict[str, Any],
        realtime_quote,
        chip_data: Optional[ChipDistribution],
        trend_result: Optional[TrendAnalysisResult],
        stock_name: str = "",
        flow_data: Optional[Any] = None,
        dragon_tiger_data: Optional[Any] = None,
        sector_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        增强分析上下文
        
        将实时行情、筹码分布、趋势分析结果、股票名称添加到上下文中
        
        Args:
            context: 原始上下文
            realtime_quote: 实时行情数据（UnifiedRealtimeQuote 或 None）
            chip_data: 筹码分布数据
            trend_result: 趋势分析结果
            stock_name: 股票名称
            
        Returns:
            增强后的上下文
        """
        enhanced = context.copy()
        
        # 添加股票名称
        if stock_name:
            enhanced['stock_name'] = stock_name
        elif realtime_quote and getattr(realtime_quote, 'name', None):
            enhanced['stock_name'] = realtime_quote.name
        
        # 添加实时行情（兼容不同数据源的字段差异）
        if realtime_quote:
            # 使用 getattr 安全获取字段，缺失字段返回 None 或默认值
            volume_ratio = getattr(realtime_quote, 'volume_ratio', None)
            enhanced['realtime'] = {
                'name': getattr(realtime_quote, 'name', ''),
                'price': getattr(realtime_quote, 'price', None),
                'change_pct': getattr(realtime_quote, 'change_pct', None),
                'volume_ratio': volume_ratio,
                'volume_ratio_desc': self._describe_volume_ratio(volume_ratio) if volume_ratio else '无数据',
                'turnover_rate': getattr(realtime_quote, 'turnover_rate', None),
                'pe_ratio': getattr(realtime_quote, 'pe_ratio', None),
                'pb_ratio': getattr(realtime_quote, 'pb_ratio', None),
                'total_mv': getattr(realtime_quote, 'total_mv', None),
                'circ_mv': getattr(realtime_quote, 'circ_mv', None),
                'change_60d': getattr(realtime_quote, 'change_60d', None),
                'source': getattr(realtime_quote, 'source', None),
            }
            # 移除 None 值以减少上下文大小
            enhanced['realtime'] = {k: v for k, v in enhanced['realtime'].items() if v is not None}
        
        # 添加筹码分布
        if chip_data:
            current_price = getattr(realtime_quote, 'price', 0) if realtime_quote else 0
            enhanced['chip'] = {
                'profit_ratio': chip_data.profit_ratio,
                'avg_cost': chip_data.avg_cost,
                'concentration_90': chip_data.concentration_90,
                'concentration_70': chip_data.concentration_70,
                'chip_status': chip_data.get_chip_status(current_price or 0),
            }
            
        # 添加资金流入流出
        if flow_data:
            enhanced['fund_flow'] = flow_data.to_dict()
            enhanced['fund_flow']['status'] = flow_data.get_fund_flow_status()
        
        # 添加趋势分析结果
        if trend_result:
            enhanced['trend_analysis'] = {
                'trend_status': trend_result.trend_status.value,
                'ma_alignment': trend_result.ma_alignment,
                'trend_strength': trend_result.trend_strength,
                'bias_ma5': trend_result.bias_ma5,
                'bias_ma10': trend_result.bias_ma10,
                'volume_status': trend_result.volume_status.value,
                'volume_trend': trend_result.volume_trend,
                'buy_signal': trend_result.buy_signal.value,
                'signal_score': trend_result.signal_score,
                'signal_reasons': trend_result.signal_reasons,
                'risk_factors': trend_result.risk_factors,
                # 高级技术指标 (Phase 1)
                'macd_signal': getattr(trend_result, 'macd_signal', ''),
                'rsi_signal': getattr(trend_result, 'rsi_signal', ''),
                'boll_signal': getattr(trend_result, 'boll_signal', ''),
                'kdj_signal': getattr(trend_result, 'kdj_signal', ''),
            }

        # Issue #234: Override today with realtime OHLC + trend MA for intraday analysis
        # Guard: trend_result.ma5 > 0 ensures MA calculation succeeded (data sufficient)
        if realtime_quote and trend_result and trend_result.ma5 > 0:
            price = getattr(realtime_quote, 'price', None)
            if price is not None and price > 0:
                yesterday_close = None
                if enhanced.get('yesterday') and isinstance(enhanced['yesterday'], dict):
                    yesterday_close = enhanced['yesterday'].get('close')
                orig_today = enhanced.get('today') or {}
                open_p = getattr(realtime_quote, 'open_price', None) or getattr(
                    realtime_quote, 'pre_close', None
                ) or yesterday_close or orig_today.get('open') or price
                high_p = getattr(realtime_quote, 'high', None) or price
                low_p = getattr(realtime_quote, 'low', None) or price
                vol = getattr(realtime_quote, 'volume', None)
                amt = getattr(realtime_quote, 'amount', None)
                pct = getattr(realtime_quote, 'change_pct', None)
                realtime_today = {
                    'close': price,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'ma5': trend_result.ma5,
                    'ma10': trend_result.ma10,
                    'ma20': trend_result.ma20,
                }
                if vol is not None:
                    realtime_today['volume'] = vol
                if amt is not None:
                    realtime_today['amount'] = amt
                if pct is not None:
                    realtime_today['pct_chg'] = pct
                for k, v in orig_today.items():
                    if k not in realtime_today and v is not None:
                        realtime_today[k] = v
                enhanced['today'] = realtime_today
                enhanced['ma_status'] = self._compute_ma_status(
                    price, trend_result.ma5, trend_result.ma10, trend_result.ma20
                )
                enhanced['date'] = date.today().isoformat()
                if yesterday_close is not None:
                    try:
                        yc = float(yesterday_close)
                        if yc > 0:
                            enhanced['price_change_ratio'] = round(
                                (price - yc) / yc * 100, 2
                            )
                    except (TypeError, ValueError):
                        pass
                if vol is not None and enhanced.get('yesterday'):
                    yest_vol = enhanced['yesterday'].get('volume') if isinstance(
                        enhanced['yesterday'], dict
                    ) else None
                    if yest_vol is not None:
                        try:
                            yv = float(yest_vol)
                            if yv > 0:
                                enhanced['volume_change_ratio'] = round(
                                    float(vol) / yv, 2
                                )
                        except (TypeError, ValueError):
                            pass

        # ETF/index flag for analyzer prompt (Fixes #274)
        enhanced['is_index_etf'] = SearchService.is_index_or_etf(
            context.get('code', ''), enhanced.get('stock_name', stock_name)
        )

        if dragon_tiger_data:
            enhanced['dragon_tiger'] = dragon_tiger_data.to_dict() if hasattr(dragon_tiger_data, 'to_dict') else dragon_tiger_data
        
        if sector_data:
            enhanced['sector_rotation'] = sector_data

        return enhanced

    def _analyze_with_agent(
        self, 
        code: str, 
        report_type: ReportType, 
        query_id: str,
        stock_name: str,
        realtime_quote: Any,
        chip_data: Optional[ChipDistribution],
        flow_data: Optional[Any] = None,
        dragon_tiger_data: Optional[Any] = None,
        sector_data: Optional[Dict] = None,
    ) -> Optional[AnalysisResult]:
        """
        使用 Agent 模式分析单只股票。
        """
        try:
            from src.agent.factory import build_agent_executor
            from src.agent.factory import DEFAULT_AGENT_SKILLS

            selected_strategies = list(getattr(self.config, 'agent_skills', None) or DEFAULT_AGENT_SKILLS)

            # Build executor from shared factory (ToolRegistry and SkillManager prototype are cached)
            executor = build_agent_executor(self.config, selected_strategies)

            # Build initial context to avoid redundant tool calls
            initial_context = {
                "stock_code": code,
                "stock_name": stock_name,
                "report_type": report_type.value,
                "selected_strategies": selected_strategies,
            }
            
            if realtime_quote:
                initial_context["realtime_quote"] = self._safe_to_dict(realtime_quote)
            if chip_data:
                initial_context["chip_distribution"] = self._safe_to_dict(chip_data)
            if flow_data:
                initial_context["fund_flow"] = flow_data.to_dict()
            if dragon_tiger_data:
                initial_context["dragon_tiger"] = dragon_tiger_data.to_dict() if hasattr(dragon_tiger_data, 'to_dict') else dragon_tiger_data
            if sector_data:
                initial_context["sector_rotation"] = sector_data

            # 运行 Agent
            message = f"请分析股票 {code} ({stock_name})，并生成决策仪表盘报告。"
            agent_result = executor.run(message, context=initial_context)

            # 转换为 AnalysisResult
            result = self._agent_result_to_analysis_result(agent_result, code, stock_name, report_type, query_id)

            # 保存新闻情报到数据库（Agent 工具结果仅用于 LLM 上下文，未持久化，Fixes #396）
            # 使用 search_stock_news（与 Agent 工具调用逻辑一致），仅 1 次 API 调用，无额外延迟
            self.intel_coordinator.persist_latest_news_for_agent(
                code=code,
                stock_name=stock_name,
                query_id=query_id,
                max_results=5,
            )

            # 保存分析历史记录
            if result:
                try:
                    self.persistence.save_analysis_history(
                        result=result,
                        query_id=query_id,
                        report_type=report_type.value,
                        news_content=None,
                        context_snapshot=initial_context,
                    )
                except Exception as e:
                    logger.warning(f"[{code}] 保存 Agent 分析历史失败: {e}")

            return result

        except Exception as e:
            logger.error(f"[{code}] Agent 分析失败: {e}")
            logger.exception(f"[{code}] Agent 详细错误信息:")
            return None

    def _agent_result_to_analysis_result(
        self, agent_result, code: str, stock_name: str, report_type: ReportType, query_id: str
    ) -> AnalysisResult:
        """
        将 AgentResult 转换为 AnalysisResult。
        """
        result = AnalysisResult(
            code=code,
            name=stock_name,
            sentiment_score=50,
            trend_prediction="未知",
            operation_advice="观望",
            success=agent_result.success,
            error_message=agent_result.error if not agent_result.success else None,
            data_sources=f"agent:{agent_result.provider}"
        )

        if agent_result.success and agent_result.dashboard:
            dash = agent_result.dashboard
            result.sentiment_score = self._safe_int(dash.get("sentiment_score"), 50)
            result.trend_prediction = dash.get("trend_prediction", "未知")
            result.operation_advice = dash.get("operation_advice", "观望")
            result.decision_type = dash.get("decision_type", "hold")
            result.analysis_summary = dash.get("analysis_summary", "")
            # The AI returns a top-level dict that contains a nested 'dashboard' sub-key
            # with core_conclusion / battle_plan / intelligence.  AnalysisResult's helper
            # methods (get_sniper_points, get_core_conclusion, etc.) expect that inner
            # structure, so we unwrap it here.
            result.dashboard = dash.get("dashboard") or dash
        else:
            result.sentiment_score = 50
            result.operation_advice = "观望"
            if not result.error_message:
                result.error_message = "Agent 未能生成有效的决策仪表盘"

        return result

    @staticmethod
    def _safe_int(value: Any, default: int = 50) -> int:
        """安全地将值转换为整数。"""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            import re
            match = re.search(r'-?\d+', value)
            if match:
                return int(match.group())
        return default
    
    def _describe_volume_ratio(self, volume_ratio: float) -> str:
        """
        量比描述
        
        量比 = 当前成交量 / 过去5日平均成交量
        """
        if volume_ratio < 0.5:
            return "极度萎缩"
        elif volume_ratio < 0.8:
            return "明显萎缩"
        elif volume_ratio < 1.2:
            return "正常"
        elif volume_ratio < 2.0:
            return "温和放量"
        elif volume_ratio < 3.0:
            return "明显放量"
        else:
            return "巨量"

    @staticmethod
    def _compute_ma_status(close: float, ma5: float, ma10: float, ma20: float) -> str:
        """
        Compute MA alignment status from price and MA values.
        Logic mirrors storage._analyze_ma_status (Issue #234).
        """
        close = close or 0
        ma5 = ma5 or 0
        ma10 = ma10 or 0
        ma20 = ma20 or 0
        if close > ma5 > ma10 > ma20 > 0:
            return "多头排列 📈"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "空头排列 📉"
        elif close > ma5 and ma5 > ma10:
            return "短期向好 🔼"
        elif close < ma5 and ma5 < ma10:
            return "短期走弱 🔽"
        else:
            return "震荡整理 ↔️"

    def _augment_historical_with_realtime(
        self, df: pd.DataFrame, realtime_quote: Any, code: str
    ) -> pd.DataFrame:
        """
        Augment historical OHLCV with today's realtime quote for intraday MA calculation.
        Issue #234: Use realtime price instead of yesterday's close for technical indicators.
        """
        if df is None or df.empty or 'close' not in df.columns:
            return df
        if realtime_quote is None:
            return df
        price = getattr(realtime_quote, 'price', None)
        if price is None or not (isinstance(price, (int, float)) and price > 0):
            return df

        # Optional: skip augmentation on non-trading days (fail-open)
        enable_realtime_tech = getattr(
            self.config, 'enable_realtime_technical_indicators', True
        )
        if not enable_realtime_tech:
            return df
        market = get_market_for_stock(code)
        if market and not is_market_open(market, date.today()):
            return df

        last_val = df['date'].max()
        last_date = (
            last_val.date() if hasattr(last_val, 'date') else
            (last_val if isinstance(last_val, date) else pd.Timestamp(last_val).date())
        )
        yesterday_close = float(df.iloc[-1]['close']) if len(df) > 0 else price
        open_p = getattr(realtime_quote, 'open_price', None) or getattr(
            realtime_quote, 'pre_close', None
        ) or yesterday_close
        high_p = getattr(realtime_quote, 'high', None) or price
        low_p = getattr(realtime_quote, 'low', None) or price
        vol = getattr(realtime_quote, 'volume', None) or 0
        amt = getattr(realtime_quote, 'amount', None)
        pct = getattr(realtime_quote, 'change_pct', None)

        if last_date >= date.today():
            # Update last row with realtime close (copy to avoid mutating caller's df)
            df = df.copy()
            idx = df.index[-1]
            df.loc[idx, 'close'] = price
            if open_p is not None:
                df.loc[idx, 'open'] = open_p
            if high_p is not None:
                df.loc[idx, 'high'] = high_p
            if low_p is not None:
                df.loc[idx, 'low'] = low_p
            if vol:
                df.loc[idx, 'volume'] = vol
            if amt is not None:
                df.loc[idx, 'amount'] = amt
            if pct is not None:
                df.loc[idx, 'pct_chg'] = pct
        else:
            # Append virtual today row
            new_row = {
                'code': code,
                'date': date.today(),
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': price,
                'volume': vol,
                'amount': amt if amt is not None else 0,
                'pct_chg': pct if pct is not None else 0,
            }
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
        return df

    @staticmethod
    def _safe_to_dict(value: Any) -> Optional[Dict[str, Any]]:
        """
        安全转换为字典
        """
        if value is None:
            return None
        if hasattr(value, "to_dict"):
            try:
                return value.to_dict()
            except Exception:
                return None
        if hasattr(value, "__dict__"):
            try:
                return dict(value.__dict__)
            except Exception:
                return None
        return None

    def _resolve_query_source(self, query_source: Optional[str]) -> str:
        """
        解析请求来源。

        优先级（从高到低）：
        1. 显式传入的 query_source：调用方明确指定时优先使用，便于覆盖推断结果或兼容未来 source_message 来自非 bot 的场景
        2. 存在 source_message 时推断为 "bot"：当前约定为机器人会话上下文
        3. 存在 query_id 时推断为 "web"：Web 触发的请求会带上 query_id
        4. 默认 "system"：定时任务或 CLI 等无上述上下文时

        Args:
            query_source: 调用方显式指定的来源，如 "bot" / "web" / "cli" / "system"

        Returns:
            归一化后的来源标识字符串，如 "bot" / "web" / "cli" / "system"
        """
        if query_source:
            return query_source
        if self.source_message:
            return "bot"
        if self.query_id:
            return "web"
        return "system"

    def _build_query_context(self, query_id: Optional[str] = None) -> Dict[str, str]:
        """
        生成用户查询关联信息
        """
        effective_query_id = query_id or self.query_id or ""

        context: Dict[str, str] = {
            "query_id": effective_query_id,
            "query_source": self.query_source or "",
        }

        if self.source_message:
            context.update({
                "requester_platform": self.source_message.platform or "",
                "requester_user_id": self.source_message.user_id or "",
                "requester_user_name": self.source_message.user_name or "",
                "requester_chat_id": self.source_message.chat_id or "",
                "requester_message_id": self.source_message.message_id or "",
                "requester_query": self.source_message.content or "",
            })

        return context
    
    def process_single_stock(
        self,
        code: str,
        skip_analysis: bool = False,
        single_stock_notify: bool = False,
        report_type: ReportType = ReportType.SIMPLE,
        analysis_query_id: Optional[str] = None,
    ) -> Optional[AnalysisResult]:
        """
        处理单只股票的完整流程

        包括：
        1. 获取数据
        2. 保存数据
        3. AI 分析
        4. 单股推送（可选，#55）

        此方法会被线程池调用，需要处理好异常

        Args:
            analysis_query_id: 查询链路关联 id
            code: 股票代码
            skip_analysis: 是否跳过 AI 分析
            single_stock_notify: 是否启用单股推送模式（每分析完一只立即推送）
            report_type: 报告类型枚举（从配置读取，Issue #119）

        Returns:
            AnalysisResult 或 None
        """
        logger.info(f"========== 开始处理 {code} ==========")
        
        try:
            # Step 1: 获取并保存数据
            success, error = self.fetch_and_save_stock_data(code)
            
            if not success:
                logger.warning(f"[{code}] 数据获取失败: {error}")
                # 即使获取失败，也尝试用已有数据分析
            
            # Step 2: AI 分析
            if skip_analysis:
                logger.info(f"[{code}] 跳过 AI 分析（dry-run 模式）")
                return None
            
            effective_query_id = analysis_query_id or self.query_id or uuid.uuid4().hex
            result = self.analyze_stock(code, report_type, query_id=effective_query_id)
            
            if result:
                data_age_days = self._get_data_age_days(
                    code,
                    context_date_hint=getattr(result, "context_date_hint", None),
                )
                self._apply_stale_data_guard(
                    result=result,
                    code=code,
                    data_age_days=data_age_days,
                    fetch_success=success,
                )
                logger.info(
                    f"[{code}] 分析完成: {result.operation_advice}, "
                    f"评分 {result.sentiment_score}"
                )
                
                # 单股推送模式（#55）：每分析完一只股票立即推送
                if single_stock_notify and self.notifier.is_available():
                    try:
                        if self.delivery_service.send_single_stock_report(
                            code=code,
                            result=result,
                            report_type=report_type,
                        ):
                            logger.info(f"[{code}] 单股推送成功")
                        else:
                            logger.warning(f"[{code}] 单股推送失败")
                    except Exception as e:
                        logger.error(f"[{code}] 单股推送异常: {e}")
            
            return result
            
        except Exception as e:
            # 捕获所有异常，确保单股失败不影响整体
            logger.exception(f"[{code}] 处理过程发生未知异常: {e}")
            return None

    def _get_data_age_days(self, code: str, context_date_hint: Any = None) -> Optional[int]:
        """Return age in days for latest available context date."""
        if context_date_hint not in (None, ""):
            return self._get_quality_guard().compute_data_age_days_from_context_date(
                context_date_hint,
                code=code,
            )
        return self._get_quality_guard().get_data_age_days(code=code, persistence=self.persistence)

    def _apply_stale_data_guard(
        self,
        *,
        result: AnalysisResult,
        code: str,
        data_age_days: Optional[int],
        fetch_success: bool,
    ) -> None:
        """
        Downgrade advice when market data is stale to reduce false confidence.
        """
        self._get_quality_guard().apply_stale_data_guard(
            result=result,
            code=code,
            data_age_days=data_age_days,
            fetch_success=fetch_success,
        )

    def _get_quality_guard(self) -> AnalysisQualityGuard:
        """Return quality guard, creating a fallback instance for tests."""
        guard = getattr(self, "quality_guard", None)
        if guard is None:
            guard = AnalysisQualityGuard(config=getattr(self, "config", None), logger=logger)
            self.quality_guard = guard
        return guard
    
    def run(
        self,
        stock_codes: Optional[List[str]] = None,
        dry_run: bool = False,
        send_notification: bool = True,
        merge_notification: bool = False
    ) -> List[AnalysisResult]:
        """
        运行完整的分析流程

        流程：
        1. 获取待分析的股票列表
        2. 使用线程池并发处理
        3. 收集分析结果
        4. 发送通知

        Args:
            stock_codes: 股票代码列表（可选，默认使用配置中的自选股）
            dry_run: 是否仅获取数据不分析
            send_notification: 是否发送推送通知
            merge_notification: 是否合并推送（跳过本次推送，由 main 层合并个股+大盘后统一发送，Issue #190）

        Returns:
            分析结果列表
        """
        start_time = time.time()
        
        # 使用配置中的股票列表
        if stock_codes is None:
            self.config.refresh_stock_list()
            stock_codes = self.config.all_stock_list
        
        if not stock_codes:
            logger.error("未配置自选股列表，请在 .env 文件中设置 STOCK_LIST / HK_STOCK_LIST / US_STOCK_LIST")
            return []
        
        logger.info(f"===== 开始分析 {len(stock_codes)} 只股票 =====")
        logger.info(f"股票列表: {', '.join(stock_codes)}")

        # 优化点 2 扩展：从同步数据中智能选股
        selected_codes = []
        if getattr(self.config, 'market_sync_stock_selection_enabled', False):
            try:
                from src.services.smart_stock_selector import select_from_synced_data
                strategy = getattr(self.config, 'market_sync_selection_strategy', 'best_performer')
                count = getattr(self.config, 'market_sync_select_count', 10)
                selected_codes = select_from_synced_data(
                    strategy=strategy,
                    count=count,
                    exclude_codes=stock_codes,  # 排除已配置的的股票，避免重复
                )
                if selected_codes:
                    logger.info(f"智能选股完成：策略={strategy}, 选中 {len(selected_codes)} 只股票")
            except Exception as e:
                logger.warning(f"智能选股失败：{e}")
        
        # 合并股票列表（去重）
        if selected_codes:
            stock_codes = list(set(stock_codes + selected_codes))
            logger.info(f"合并后股票数量：{len(stock_codes)} (基础池：{len(stock_codes) - len(selected_codes)}, 智能选股：{len(selected_codes)})")
        
        # === 批量预取实时行情（优化：避免每只股票都触发全量拉取）===
        # 只有股票数量 >= 5 时才进行预取，少量股票直接逐个查询更高效
        if len(stock_codes) >= 5:
            prefetch_count = self.fetcher_manager.prefetch_realtime_quotes(stock_codes)
            if prefetch_count > 0:
                logger.info(f"已启用批量预取架构：一次拉取全市场数据，{len(stock_codes)} 只股票共享缓存")
        
        # 单股推送模式（#55）：从配置读取
        single_stock_notify = getattr(self.config, 'single_stock_notify', False)
        # Issue #119: 从配置读取报告类型
        report_type_str = getattr(self.config, 'report_type', 'simple').lower()
        report_type = ReportType.FULL if report_type_str == 'full' else ReportType.SIMPLE
        # Issue #128: 从配置读取分析间隔
        analysis_delay = getattr(self.config, 'analysis_delay', 0)

        if single_stock_notify:
            logger.info(f"已启用单股推送模式：每分析完一只股票立即推送（报告类型: {report_type_str}）")
        
        results: List[AnalysisResult] = []
        
        # 使用线程池并发处理

        # 优化点 7：根据股票数量动态调整并发数
        stock_count = len(stock_codes)
        if stock_count >= 20:
            # 大量股票：使用较高并发
            dynamic_workers = min(10, stock_count)
        elif stock_count >= 10:
            # 中等数量：适中并发
            dynamic_workers = min(7, stock_count)
        else:
            # 少量股票：保持配置默认值
            dynamic_workers = self.max_workers

        # 实际使用的并发数（不超过配置最大值）
        actual_workers = min(dynamic_workers, self.max_workers)
        logger.info(f"并发数：{actual_workers} (配置：{self.max_workers})")

        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            # 提交任务
            future_to_code = {
                executor.submit(
                    self.process_single_stock,
                    code,
                    skip_analysis=dry_run,
                    single_stock_notify=single_stock_notify and send_notification,
                    report_type=report_type,  # Issue #119: 传递报告类型
                    analysis_query_id=uuid.uuid4().hex,
                ): code
                for code in stock_codes
            }
            
            # 收集结果
            for idx, future in enumerate(as_completed(future_to_code)):
                code = future_to_code[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)

                    # Issue #128: 分析间隔 - 在个股分析和大盘分析之间添加延迟
                    if idx < len(stock_codes) - 1 and analysis_delay > 0:
                        logger.debug(f"等待 {analysis_delay} 秒后继续下一只股票...")
                        time.sleep(analysis_delay)

                except Exception as e:
                    logger.error(f"[{code}] 任务执行失败: {e}")
        
        # 统计
        elapsed_time = time.time() - start_time
        
        # dry-run 模式下，数据获取成功即视为成功
        if dry_run:
            # 检查哪些股票的数据今天已存在
            success_count = self.persistence.count_codes_with_today_data(stock_codes)
            fail_count = len(stock_codes) - success_count
        else:
            success_count = len(results)
            fail_count = len(stock_codes) - success_count
        
        logger.info("===== 分析完成 =====")
        logger.info(f"成功: {success_count}, 失败: {fail_count}, 耗时: {elapsed_time:.2f} 秒")
        
        # 发送通知（单股推送模式下跳过汇总推送，避免重复）
        if results and send_notification and not dry_run:
            if single_stock_notify:
                # 单股推送模式：只保存汇总报告，不再重复推送
                logger.info("单股推送模式：跳过汇总推送，仅保存报告到本地")
                self._send_notifications(results, skip_push=True)
            elif merge_notification:
                # 合并模式（Issue #190）：仅保存，不推送，由 main 层合并个股+大盘后统一发送
                logger.info("合并推送模式：跳过本次推送，将在个股+大盘复盘后统一发送")
                self._send_notifications(results, skip_push=True)
            else:
                self._send_notifications(results)
        
        return results
    
    def _send_notifications(self, results: List[AnalysisResult], skip_push: bool = False) -> None:
        """
        发送分析结果通知
        
        生成决策仪表盘格式的报告
        
        Args:
            results: 分析结果列表
            skip_push: 是否跳过推送（仅保存到本地，用于单股推送模式）
        """
        self.delivery_service.send_batch_notifications(results, skip_push=skip_push)
