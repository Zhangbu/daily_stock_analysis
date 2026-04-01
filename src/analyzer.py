# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - AI分析层
===================================

职责：
1. 封装 Gemini API 调用逻辑
2. 利用 Google Search Grounding 获取实时新闻
3. 结合技术面和消息面生成分析报告
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from src.agent.llm_adapter import get_thinking_extra_body
from src.config import get_config
from src.llm.providers import (
    init_anthropic_fallback,
    init_gemini_model,
    init_openai_fallback,
    switch_to_gemini_fallback_model,
)
from src.llm.retry_policy import (
    clip_text as _clip_text,
    is_ascii_encode_error as _is_ascii_encode_error,
    is_non_retryable_llm_error as _is_non_retryable_llm_error,
    safe_exception_text as _safe_exception_text,
)
from src.llm.result_parser import fix_json_string, parse_response, parse_text_response
from src.llm.response_cache import get_llm_cache, LLMResponseCache

logger = logging.getLogger(__name__)

_ASCII_UNSAFE_TABLE_CHARS = {
    0x2502: "|",  # │
    0x2503: "|",  # ┃
    0x2506: "|",  # ┆
    0x2507: "|",  # ┇
    0x250A: "|",  # ┊
    0x250B: "|",  # ┋
    0x254E: "|",  # ╎
    0x254F: "|",  # ╏
    0x2500: "-",  # ─
    0x2501: "-",  # ━
    0x2504: "-",  # ┄
    0x2505: "-",  # ┅
    0x2508: "-",  # ┈
    0x2509: "-",  # ┉
    0x2550: "=",  # ═
    0x256A: "+",  # ╪
    0x256B: "+",  # ╫
    0x256C: "+",  # ╬
    0x253C: "+",  # ┼
    0x256D: "+",  # ╭
    0x256E: "+",  # ╮
    0x256F: "+",  # ╯
    0x2570: "+",  # ╰
    0x250C: "+",  # ┌
    0x2510: "+",  # ┐
    0x2514: "+",  # └
    0x2518: "+",  # ┘
}


def _sanitize_ascii_unsafe_text(text: str) -> str:
    """Normalize common box-drawing characters for strict ASCII encoders."""
    return text.translate(_ASCII_UNSAFE_TABLE_CHARS)


# 股票名称映射（常见股票）
STOCK_NAME_MAP = {
    # === A股 ===
    '600519': '贵州茅台',
    '000001': '平安银行',
    '300750': '宁德时代',
    '002594': '比亚迪',
    '600036': '招商银行',
    '601318': '中国平安',
    '000858': '五粮液',
    '600276': '恒瑞医药',
    '601012': '隆基绿能',
    '002475': '立讯精密',
    '300059': '东方财富',
    '002415': '海康威视',
    '600900': '长江电力',
    '601166': '兴业银行',
    '600028': '中国石化',

    # === 美股 ===
    'AAPL': '苹果',
    'TSLA': '特斯拉',
    'MSFT': '微软',
    'GOOGL': '谷歌A',
    'GOOG': '谷歌C',
    'AMZN': '亚马逊',
    'NVDA': '英伟达',
    'META': 'Meta',
    'AMD': 'AMD',
    'INTC': '英特尔',
    'BABA': '阿里巴巴',
    'PDD': '拼多多',
    'JD': '京东',
    'BIDU': '百度',
    'NIO': '蔚来',
    'XPEV': '小鹏汽车',
    'LI': '理想汽车',
    'COIN': 'Coinbase',
    'MSTR': 'MicroStrategy',

    # === 港股 (5位数字) ===
    '00700': '腾讯控股',
    '03690': '美团',
    '01810': '小米集团',
    '09988': '阿里巴巴',
    '09618': '京东集团',
    '09888': '百度集团',
    '01024': '快手',
    '00981': '中芯国际',
    '02015': '理想汽车',
    '09868': '小鹏汽车',
    '00005': '汇丰控股',
    '01299': '友邦保险',
    '00941': '中国移动',
    '00883': '中国海洋石油',
}


def get_stock_name_multi_source(
    stock_code: str,
    context: Optional[Dict] = None,
    data_manager = None
) -> str:
    """
    多来源获取股票中文名称

    获取策略（按优先级）：
    1. 从传入的 context 中获取（realtime 数据）
    2. 从静态映射表 STOCK_NAME_MAP 获取
    3. 从 DataFetcherManager 获取（各数据源）
    4. 返回默认名称（股票+代码）

    Args:
        stock_code: 股票代码
        context: 分析上下文（可选）
        data_manager: DataFetcherManager 实例（可选）

    Returns:
        股票中文名称
    """
    # 1. 从上下文获取（实时行情数据）
    if context:
        # 优先从 stock_name 字段获取
        if context.get('stock_name'):
            name = context['stock_name']
            if name and not name.startswith('股票'):
                return name

        # 其次从 realtime 数据获取
        if 'realtime' in context and context['realtime'].get('name'):
            return context['realtime']['name']

    # 2. 从静态映射表获取
    if stock_code in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[stock_code]

    # 3. 从数据源获取
    if data_manager is None:
        try:
            from data_provider.base import DataFetcherManager
            data_manager = DataFetcherManager()
        except Exception as e:
            logger.debug(f"无法初始化 DataFetcherManager: {e}")

    if data_manager:
        try:
            name = data_manager.get_stock_name(stock_code)
            if name:
                # 更新缓存
                STOCK_NAME_MAP[stock_code] = name
                return name
        except Exception as e:
            logger.debug(f"从数据源获取股票名称失败: {e}")

    # 4. 返回默认名称
    return f'股票{stock_code}'


@dataclass
class AnalysisResult:
    """
    AI 分析结果数据类 - 决策仪表盘版

    封装 Gemini 返回的分析结果，包含决策仪表盘和详细分析
    """
    code: str
    name: str

    # ========== 核心指标 ==========
    sentiment_score: int  # 综合评分 0-100 (>70强烈看多, >60看多, 40-60震荡, <40看空)
    trend_prediction: str  # 趋势预测：强烈看多/看多/震荡/看空/强烈看空
    operation_advice: str  # 操作建议：买入/加仓/持有/减仓/卖出/观望
    decision_type: str = "hold"  # 决策类型：buy/hold/sell（用于统计）
    confidence_level: str = "中"  # 置信度：高/中/低

    # ========== 决策仪表盘 (新增) ==========
    dashboard: Optional[Dict[str, Any]] = None  # 完整的决策仪表盘数据

    # ========== 走势分析 ==========
    trend_analysis: str = ""  # 走势形态分析（支撑位、压力位、趋势线等）
    short_term_outlook: str = ""  # 短期展望（1-3日）
    medium_term_outlook: str = ""  # 中期展望（1-2周）

    # ========== 技术面分析 ==========
    technical_analysis: str = ""  # 技术指标综合分析
    ma_analysis: str = ""  # 均线分析（多头/空头排列，金叉/死叉等）
    volume_analysis: str = ""  # 量能分析（放量/缩量，主力动向等）
    pattern_analysis: str = ""  # K线形态分析

    # ========== 基本面分析 ==========
    fundamental_analysis: str = ""  # 基本面综合分析
    sector_position: str = ""  # 板块地位和行业趋势
    company_highlights: str = ""  # 公司亮点/风险点

    # ========== 情绪面/消息面分析 ==========
    news_summary: str = ""  # 近期重要新闻/公告摘要
    market_sentiment: str = ""  # 市场情绪分析
    hot_topics: str = ""  # 相关热点话题

    # ========== 综合分析 ==========
    analysis_summary: str = ""  # 综合分析摘要
    key_points: str = ""  # 核心看点（3-5个要点）
    risk_warning: str = ""  # 风险提示
    buy_reason: str = ""  # 买入/卖出理由

    # ========== 元数据 ==========
    market_snapshot: Optional[Dict[str, Any]] = None  # 当日行情快照（展示用）
    raw_response: Optional[str] = None  # 原始响应（调试用）
    search_performed: bool = False  # 是否执行了联网搜索
    data_sources: str = ""  # 数据来源说明
    success: bool = True
    error_message: Optional[str] = None

    # ========== 价格数据（分析时快照）==========
    current_price: Optional[float] = None  # 分析时的股价
    change_pct: Optional[float] = None     # 分析时的涨跌幅(%)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'sentiment_score': self.sentiment_score,
            'trend_prediction': self.trend_prediction,
            'operation_advice': self.operation_advice,
            'decision_type': self.decision_type,
            'confidence_level': self.confidence_level,
            'dashboard': self.dashboard,  # 决策仪表盘数据
            'trend_analysis': self.trend_analysis,
            'short_term_outlook': self.short_term_outlook,
            'medium_term_outlook': self.medium_term_outlook,
            'technical_analysis': self.technical_analysis,
            'ma_analysis': self.ma_analysis,
            'volume_analysis': self.volume_analysis,
            'pattern_analysis': self.pattern_analysis,
            'fundamental_analysis': self.fundamental_analysis,
            'sector_position': self.sector_position,
            'company_highlights': self.company_highlights,
            'news_summary': self.news_summary,
            'market_sentiment': self.market_sentiment,
            'hot_topics': self.hot_topics,
            'analysis_summary': self.analysis_summary,
            'key_points': self.key_points,
            'risk_warning': self.risk_warning,
            'buy_reason': self.buy_reason,
            'market_snapshot': self.market_snapshot,
            'search_performed': self.search_performed,
            'success': self.success,
            'error_message': self.error_message,
            'current_price': self.current_price,
            'change_pct': self.change_pct,
        }

    def get_core_conclusion(self) -> str:
        """获取核心结论（一句话）"""
        if self.dashboard and 'core_conclusion' in self.dashboard:
            return self.dashboard['core_conclusion'].get('one_sentence', self.analysis_summary)
        return self.analysis_summary

    def get_position_advice(self, has_position: bool = False) -> str:
        """获取持仓建议"""
        if self.dashboard and 'core_conclusion' in self.dashboard:
            pos_advice = self.dashboard['core_conclusion'].get('position_advice', {})
            if has_position:
                return pos_advice.get('has_position', self.operation_advice)
            return pos_advice.get('no_position', self.operation_advice)
        return self.operation_advice

    def get_sniper_points(self) -> Dict[str, str]:
        """获取狙击点位"""
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('sniper_points', {})
        return {}

    def get_checklist(self) -> List[str]:
        """获取检查清单"""
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('action_checklist', [])
        return []

    def get_risk_alerts(self) -> List[str]:
        """获取风险警报"""
        if self.dashboard and 'intelligence' in self.dashboard:
            return self.dashboard['intelligence'].get('risk_alerts', [])
        return []

    def get_emoji(self) -> str:
        """根据操作建议返回对应 emoji"""
        emoji_map = {
            '买入': '🟢',
            '加仓': '🟢',
            '强烈买入': '💚',
            '持有': '🟡',
            '观望': '⚪',
            '减仓': '🟠',
            '卖出': '🔴',
            '强烈卖出': '❌',
        }
        advice = self.operation_advice or ''
        # Direct match first
        if advice in emoji_map:
            return emoji_map[advice]
        # Handle compound advice like "卖出/观望" — use the first part
        for part in advice.replace('/', '|').split('|'):
            part = part.strip()
            if part in emoji_map:
                return emoji_map[part]
        # Score-based fallback
        score = self.sentiment_score
        if score >= 80:
            return '💚'
        elif score >= 65:
            return '🟢'
        elif score >= 55:
            return '🟡'
        elif score >= 45:
            return '⚪'
        elif score >= 35:
            return '🟠'
        else:
            return '🔴'

    def get_confidence_stars(self) -> str:
        """返回置信度星级"""
        star_map = {'高': '⭐⭐⭐', '中': '⭐⭐', '低': '⭐'}
        return star_map.get(self.confidence_level, '⭐⭐')


class GeminiAnalyzer:
    """
    Gemini AI 分析器

    职责：
    1. 调用 Google Gemini API 进行股票分析
    2. 结合预先搜索的新闻和技术面数据生成分析报告
    3. 解析 AI 返回的 JSON 格式结果

    使用方式：
        analyzer = GeminiAnalyzer()
        result = analyzer.analyze(context, news_context)
    """

    # ========================================
    # 系统提示词 - 决策仪表盘 v2.0
    # ========================================
    # 输出格式升级：从简单信号升级为决策仪表盘
    # 核心模块：核心结论 + 数据透视 + 舆情情报 + 作战计划
    # ========================================

    SYSTEM_PROMPT = """你是一位趋势交易分析师，任务是基于输入数据输出严格合法的【决策仪表盘】JSON。

规则：
- 只输出 JSON，不要补充解释、Markdown、代码块。
- 缺失数据直接写明“数据缺失，无法判断”，禁止编造。
- 先给结论，再给证据、风险和行动方案。
- 默认遵循趋势交易：优先 MA5 > MA10 > MA20，多头优于震荡，震荡优于空头。
- 乖离率 > 5% 默认判为追高风险；< 2% 最优，2-5% 可谨慎参与。
- 缩量回踩支撑、放量突破、筹码健康、无重大利空时可提高评分。
- 跌破 MA20、空头排列、放量下跌、重大利空时优先降级为观望/减仓/卖出。
- 风险排查至少覆盖：减持、业绩恶化、监管处罚、政策利空、解禁、估值过高。
- 强势趋势股可适度放宽乖离率，但必须保留止损和仓位控制。
- 若标的是指数/ETF，只分析指数走势、跟踪误差和流动性，不讨论基金管理人经营风险。

评分参考：
- 80-100：多头排列、低乖离率、量价配合、筹码健康、消息偏利好。
- 60-79：趋势较好，乖离率 < 5%，允许少量次要瑕疵。
- 40-59：趋势不清、追高风险或存在明显风险事件。
- 0-39：空头排列、跌破关键均线、放量走弱或重大利空。

必须输出以下顶层字段：
- stock_name, sentiment_score, trend_prediction, operation_advice, decision_type, confidence_level
- dashboard, analysis_summary, key_points, risk_warning, buy_reason
- trend_analysis, short_term_outlook, medium_term_outlook, technical_analysis, ma_analysis
- volume_analysis, pattern_analysis, fundamental_analysis, sector_position, company_highlights
- news_summary, market_sentiment, hot_topics, search_performed, data_sources

dashboard 结构必须包含：
- core_conclusion: one_sentence, signal_type, time_sensitivity, position_advice(no_position, has_position)
- data_perspective: trend_status, price_position, volume_analysis, chip_structure
- intelligence: latest_news, risk_alerts, positive_catalysts, earnings_outlook, sentiment_summary
- battle_plan: sniper_points, position_strategy, action_checklist

字段要求：
- one_sentence: 30字以内，直接说明该买/该卖/该等。
- signal_type: 只能是“🟢买入信号/🟡持有观望/🔴卖出信号/⚠️风险警告”之一。
- decision_type: 只能是 buy / hold / sell。
- operation_advice: 只能是 买入/加仓/持有/减仓/卖出/观望。
- confidence_level: 只能是 高/中/低。
- action_checklist: 每项以 ✅/⚠️/❌ 开头。
- risk_alerts 和 positive_catalysts: 数组；无内容时返回空数组。
- 支撑位、压力位、买点、止损、止盈尽量给具体价格。
- 股票名称必须是正确中文名；若输入名称错误，按正确名称输出。

输出前自检：
- JSON 合法且字段齐全。
- 结论与评分、风险、仓位建议一致。
- 没有编造缺失数据，没有输出 schema 说明。"""
    _MAX_PROMPT_NEWS_CHARS = 1000  # 从 1800 降至 1000，减少 token 使用
    _MAX_PROMPT_NEWS_LINES = 12    # 从 18 降至 12
    _MAX_PROMPT_BULLET_ITEMS = 3
    _MAX_PROMPT_ITEM_CHARS = 90

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 AI 分析器

        优先级：Gemini > Anthropic > OpenAI

        Args:
            api_key: Gemini API Key（可选，默认从配置读取）
        """
        config = get_config()
        self._api_key = api_key or config.gemini_api_key
        self._model = None
        self._current_model_name = None  # 当前使用的模型名称
        self._using_fallback = False  # 是否正在使用备选模型
        self._use_openai = False  # 是否使用 OpenAI 兼容 API
        self._use_anthropic = False  # 是否使用 Anthropic Claude API
        self._openai_client = None  # OpenAI 客户端
        self._anthropic_client = None  # Anthropic 客户端

        # 检查 Gemini API Key 是否有效（过滤占位符）
        gemini_key_valid = self._api_key and not self._api_key.startswith('your_') and len(self._api_key) > 10

        # 优先级：Gemini > Anthropic > OpenAI
        if gemini_key_valid:
            try:
                self._init_model()
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}, trying Anthropic then OpenAI")
                self._try_anthropic_then_openai()
        else:
            logger.info("Gemini API Key not configured, trying Anthropic then OpenAI")
            self._try_anthropic_then_openai()

        if not self._model and not self._anthropic_client and not self._openai_client:
            logger.warning("No AI API Key configured, AI analysis will be unavailable")

    def _try_anthropic_then_openai(self) -> None:
        """优先尝试 Anthropic，其次 OpenAI 作为备选。两者均初始化以供运行时互为故障转移（如 Anthropic 429 时切 OpenAI）。"""
        self._init_anthropic_fallback()
        self._init_openai_fallback()

    def _init_anthropic_fallback(self) -> None:
        """
        初始化 Anthropic Claude API 作为备选。

        使用 Anthropic Messages API：https://docs.anthropic.com/en/api/messages
        """
        init_anthropic_fallback(self, get_config())

    def _init_openai_fallback(self) -> None:
        """
        初始化 OpenAI 兼容 API 作为备选

        支持所有 OpenAI 格式的 API，包括：
        - OpenAI 官方
        - DeepSeek
        - 通义千问
        - Moonshot 等
        """
        init_openai_fallback(self, get_config())

    def _init_model(self) -> None:
        """
        初始化 Gemini 模型

        配置：
        - 使用 gemini-3-flash-preview 或 gemini-2.5-flash 模型
        - 不启用 Google Search（使用外部 Tavily/SerpAPI 搜索）
        """
        init_gemini_model(self, get_config())

    def _switch_to_fallback_model(self) -> bool:
        """
        切换到备选模型

        Returns:
            是否成功切换
        """
        return switch_to_gemini_fallback_model(self, get_config())

    def is_available(self) -> bool:
        """检查分析器是否可用。"""
        return (
            self._model is not None
            or self._anthropic_client is not None
            or self._openai_client is not None
        )

    def _call_anthropic_api(self, prompt: str, generation_config: dict) -> str:
        """
        调用 Anthropic Claude Messages API。

        Args:
            prompt: 用户提示词
            generation_config: 生成配置（temperature, max_output_tokens）

        Returns:
            响应文本
        """
        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay
        temperature = generation_config.get(
            'temperature', config.anthropic_temperature
        )
        max_tokens = generation_config.get('max_output_tokens', config.anthropic_max_tokens)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay = min(delay, 60)
                    logger.info(
                        f"[Anthropic] Retry {attempt + 1}/{max_retries}, "
                        f"waiting {delay:.1f}s..."
                    )
                    time.sleep(delay)

                message = self._anthropic_client.messages.create(
                    model=self._current_model_name,
                    max_tokens=max_tokens,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                if (
                    message.content
                    and len(message.content) > 0
                    and hasattr(message.content[0], 'text')
                ):
                    return message.content[0].text
                raise ValueError("Anthropic API returned empty response")
            except Exception as e:
                if _is_non_retryable_llm_error(e):
                    logger.error(
                        "[Anthropic] 检测到不可恢复错误，跳过重试: %s",
                        _clip_text(_safe_exception_text(e), 160),
                    )
                    raise
                error_str = str(e)
                is_rate_limit = (
                    '429' in error_str
                    or 'rate' in error_str.lower()
                    or 'quota' in error_str.lower()
                )
                if is_rate_limit:
                    logger.warning(
                        f"[Anthropic] Rate limit, attempt {attempt + 1}/"
                        f"{max_retries}: {error_str[:100]}"
                    )
                else:
                    logger.warning(
                        f"[Anthropic] API failed, attempt {attempt + 1}/"
                        f"{max_retries}: {error_str[:100]}"
                    )
                if attempt == max_retries - 1:
                    raise
        raise Exception("Anthropic API failed after max retries")

    def _call_openai_api(self, prompt: str, generation_config: dict) -> str:
        """
        调用 OpenAI 兼容 API

        Args:
            prompt: 提示词
            generation_config: 生成配置

        Returns:
            响应文本
        """
        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay
        system_prompt_for_openai = self.SYSTEM_PROMPT
        prompt_for_openai = prompt

        def _build_base_request_kwargs(system_prompt_text: str, user_prompt_text: str) -> dict:
            # OpenAI-compatible path (DeepSeek, Qwen, etc.): add extra_body for thinking models
            model_name = self._current_model_name
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt_text},
                    {"role": "user", "content": user_prompt_text},
                ],
                "temperature": generation_config.get('temperature', config.openai_temperature),
            }
            payload = get_thinking_extra_body(model_name)
            if payload:
                kwargs["extra_body"] = payload
            return kwargs

        def _is_unsupported_param_error(error_message: str, param_name: str) -> bool:
            lower_msg = error_message.lower()
            return ('400' in lower_msg or "unsupported parameter" in lower_msg or "unsupported param" in lower_msg) and param_name in lower_msg

        if not hasattr(self, "_token_param_mode"):
            self._token_param_mode = {}

        max_output_tokens = generation_config.get('max_output_tokens', 8192)
        model_name = self._current_model_name
        mode = self._token_param_mode.get(model_name, "max_tokens")
        last_error: Optional[Exception] = None

        def _kwargs_with_mode(mode_value):
            kwargs = _build_base_request_kwargs(system_prompt_for_openai, prompt_for_openai)
            if mode_value is not None:
                kwargs[mode_value] = max_output_tokens
            return kwargs

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay = min(delay, 60)
                    logger.info(
                        "[OpenAI] 第 %d/%d 次重试，等待 %.1f 秒 (model=%s, token_param=%s)",
                        attempt + 1,
                        max_retries,
                        delay,
                        model_name,
                        mode or "none",
                    )
                    time.sleep(delay)

                try:
                    response = self._openai_client.chat.completions.create(**_kwargs_with_mode(mode))
                except Exception as e:
                    error_str = str(e)
                    if mode == "max_tokens" and _is_unsupported_param_error(error_str, "max_tokens"):
                        logger.warning(
                            "[OpenAI] 模型不支持 max_tokens，切换为 max_completion_tokens (model=%s)",
                            model_name,
                        )
                        mode = "max_completion_tokens"
                        self._token_param_mode[model_name] = mode
                        response = self._openai_client.chat.completions.create(**_kwargs_with_mode(mode))
                    elif mode == "max_completion_tokens" and _is_unsupported_param_error(error_str, "max_completion_tokens"):
                        logger.warning(
                            "[OpenAI] 模型不支持 max_completion_tokens，移除 token 参数重试 (model=%s)",
                            model_name,
                        )
                        mode = None
                        self._token_param_mode[model_name] = mode
                        response = self._openai_client.chat.completions.create(**_kwargs_with_mode(mode))
                    else:
                        raise

                if response and response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
                else:
                    raise ValueError("OpenAI API 返回空响应")
                    
            except Exception as e:
                last_error = e
                error_str = _safe_exception_text(e)
                error_type = type(e).__name__

                # Some OpenAI-compatible providers may reject box-drawing chars
                # when an internal component incorrectly uses ASCII encoding.
                if _is_ascii_encode_error(error_str):
                    sanitized_system_prompt = _sanitize_ascii_unsafe_text(system_prompt_for_openai)
                    sanitized_prompt = _sanitize_ascii_unsafe_text(prompt_for_openai)
                    system_changed = sanitized_system_prompt != system_prompt_for_openai
                    user_changed = sanitized_prompt != prompt_for_openai
                    if (
                        system_changed
                        or user_changed
                    ):
                        system_prompt_for_openai = sanitized_system_prompt
                        prompt_for_openai = sanitized_prompt
                        logger.warning(
                            "[OpenAI] 检测到 ASCII 编码问题，已清洗请求文本后重试 "
                            "(model=%s, system_changed=%s, user_changed=%s)",
                            model_name,
                            system_changed,
                            user_changed,
                        )
                        if attempt == max_retries - 1:
                            raise
                        continue
                    logger.error(
                        "[OpenAI] ASCII 编码错误无法通过文本清洗修复，跳过重试: %s",
                        _clip_text(error_str, 160),
                    )
                    raise

                if _is_non_retryable_llm_error(e):
                    logger.error(
                        "[OpenAI] 检测到不可恢复错误，跳过重试: %s",
                        _clip_text(error_str, 160),
                    )
                    raise

                is_rate_limit = '429' in error_str or 'rate' in error_str.lower() or 'quota' in error_str.lower()
                
                if is_rate_limit:
                    logger.warning(
                        "[OpenAI] API 限流，第 %d/%d 次尝试 (model=%s, token_param=%s, error_type=%s): %s",
                        attempt + 1,
                        max_retries,
                        model_name,
                        mode or "none",
                        error_type,
                        _clip_text(error_str, 140),
                    )
                else:
                    logger.warning(
                        "[OpenAI] API 调用失败，第 %d/%d 次尝试 (model=%s, token_param=%s, error_type=%s): %s",
                        attempt + 1,
                        max_retries,
                        model_name,
                        mode or "none",
                        error_type,
                        _clip_text(error_str, 140),
                    )
                
                if attempt == max_retries - 1:
                    raise
        
        if last_error:
            raise Exception(f"OpenAI API 调用失败，已达最大重试次数: {_clip_text(_safe_exception_text(last_error), 180)}")
        raise Exception("OpenAI API 调用失败，已达最大重试次数")
    
    def _call_api_with_retry(self, prompt: str, generation_config: dict) -> str:
        """
        调用 AI API，带有重试和模型切换机制
        
        优先级：Gemini > Gemini 备选模型 > OpenAI 兼容 API
        
        处理 429 限流错误：
        1. 先指数退避重试
        2. 多次失败后切换到备选模型
        3. Gemini 完全失败后尝试 OpenAI
        
        Args:
            prompt: 提示词
            generation_config: 生成配置
            
        Returns:
            响应文本
        """
        # 若使用 Anthropic，调用 Anthropic（失败时回退到 OpenAI）
        if self._use_anthropic:
            try:
                return self._call_anthropic_api(prompt, generation_config)
            except Exception as anthropic_error:
                if self._openai_client:
                    logger.warning(
                        "[Anthropic] All retries failed, falling back to OpenAI"
                    )
                    return self._call_openai_api(prompt, generation_config)
                raise anthropic_error

        # 若使用 OpenAI（仅当无 Anthropic 时为主选）
        if self._use_openai:
            return self._call_openai_api(prompt, generation_config)

        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay
        
        last_error = None
        tried_fallback = getattr(self, '_using_fallback', False)
        
        for attempt in range(max_retries):
            try:
                # 请求前增加延时（防止请求过快触发限流）
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))  # 指数退避: 5, 10, 20, 40...
                    delay = min(delay, 60)  # 最大60秒
                    logger.info(f"[Gemini] 第 {attempt + 1} 次重试，等待 {delay:.1f} 秒...")
                    time.sleep(delay)
                
                response = self._model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options={"timeout": 120}
                )
                
                if response and response.text:
                    return response.text
                else:
                    raise ValueError("Gemini 返回空响应")
                    
            except Exception as e:
                last_error = e
                if _is_non_retryable_llm_error(e):
                    logger.error(
                        "[Gemini] 检测到不可恢复错误，停止 Gemini 重试并进入后备链路: %s",
                        _clip_text(_safe_exception_text(e), 160),
                    )
                    break
                error_str = str(e)
                
                # 检查是否是 429 限流错误
                is_rate_limit = '429' in error_str or 'quota' in error_str.lower() or 'rate' in error_str.lower()
                
                if is_rate_limit:
                    logger.warning(f"[Gemini] API 限流 (429)，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")
                    
                    # 如果已经重试了一半次数且还没切换过备选模型，尝试切换
                    if attempt >= max_retries // 2 and not tried_fallback:
                        if self._switch_to_fallback_model():
                            tried_fallback = True
                            logger.info("[Gemini] 已切换到备选模型，继续重试")
                        else:
                            logger.warning("[Gemini] 切换备选模型失败，继续使用当前模型重试")
                else:
                    # 非限流错误，记录并继续重试
                    logger.warning(f"[Gemini] API 调用失败，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")
        
        # Gemini 重试耗尽，尝试 Anthropic 再 OpenAI
        if self._anthropic_client:
            logger.warning("[Gemini] All retries failed, switching to Anthropic")
            try:
                return self._call_anthropic_api(prompt, generation_config)
            except Exception as anthropic_error:
                logger.warning(
                    f"[Anthropic] Fallback failed: {anthropic_error}"
                )
                if self._openai_client:
                    logger.warning("[Gemini] Trying OpenAI as final fallback")
                    try:
                        return self._call_openai_api(prompt, generation_config)
                    except Exception as openai_error:
                        logger.error(
                            f"[OpenAI] Final fallback also failed: {openai_error}"
                        )
                        raise last_error or anthropic_error or openai_error
                raise last_error or anthropic_error

        if self._openai_client:
            logger.warning("[Gemini] All retries failed, switching to OpenAI")
            try:
                return self._call_openai_api(prompt, generation_config)
            except Exception as openai_error:
                logger.error(f"[OpenAI] Fallback also failed: {openai_error}")
                raise last_error or openai_error
        # 懒加载 Anthropic，再尝试 OpenAI
        if config.anthropic_api_key and not self._anthropic_client:
            logger.warning("[Gemini] Trying lazy-init Anthropic API")
            self._init_anthropic_fallback()
            if self._anthropic_client:
                try:
                    return self._call_anthropic_api(prompt, generation_config)
                except Exception as ae:
                    logger.warning(f"[Anthropic] Lazy fallback failed: {ae}")
                    if self._openai_client:
                        try:
                            return self._call_openai_api(prompt, generation_config)
                        except Exception as oe:
                            raise last_error or ae or oe
                    raise last_error or ae
        if config.openai_api_key and not self._openai_client:
            logger.warning("[Gemini] Trying lazy-init OpenAI API")
            self._init_openai_fallback()
            if self._openai_client:
                try:
                    return self._call_openai_api(prompt, generation_config)
                except Exception as openai_error:
                    logger.error(f"[OpenAI] Lazy fallback also failed: {openai_error}")
                    raise last_error or openai_error

        # 所有备选均耗尽
        raise last_error or Exception("所有 AI API 调用失败，已达最大重试次数")
    
    def analyze(
        self, 
        context: Dict[str, Any],
        news_context: Optional[str] = None
    ) -> AnalysisResult:
        """
        分析单只股票
        
        流程：
        1. 格式化输入数据（技术面 + 新闻）
        2. 调用 Gemini API（带重试和模型切换）
        3. 解析 JSON 响应
        4. 返回结构化结果
        
        Args:
            context: 从 storage.get_analysis_context() 获取的上下文数据
            news_context: 预先搜索的新闻内容（可选）
            
        Returns:
            AnalysisResult 对象
        """
        code = context.get('code', 'Unknown')
        config = get_config()
        
        # 请求前增加延时（防止连续请求触发限流）
        request_delay = config.gemini_request_delay
        if request_delay > 0:
            logger.debug(f"[LLM] 请求前等待 {request_delay:.1f} 秒...")
            time.sleep(request_delay)
        
        # 优先从上下文获取股票名称（由 main.py 传入）
        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            # 备选：从 realtime 中获取
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                # 最后从映射表获取
                name = STOCK_NAME_MAP.get(code, f'股票{code}')
        
        # 如果模型不可用，返回默认结果
        if not self.is_available():
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary='AI 分析功能未启用（未配置 API Key）',
                risk_warning='请配置 Gemini API Key 后重试',
                success=False,
                error_message='Gemini API Key 未配置',
            )
        
        try:
            # 格式化输入（包含技术面数据和新闻）
            prompt = self._format_prompt(context, name, news_context)
            
            # 获取模型名称
            model_name = getattr(self, '_current_model_name', None)
            if not model_name:
                model_name = getattr(self._model, '_model_name', 'unknown')
                if hasattr(self._model, 'model_name'):
                    model_name = self._model.model_name
            
            logger.info(f"========== AI 分析 {name}({code}) ==========")
            logger.info(f"[LLM配置] 模型: {model_name}")
            logger.info(f"[LLM配置] Prompt 长度: {len(prompt)} 字符")
            logger.info(f"[LLM配置] 是否包含新闻: {'是' if news_context else '否'}")
            
            # 记录完整 prompt 到日志（INFO级别记录摘要，DEBUG记录完整）
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            logger.info(f"[LLM Prompt 预览]\n{prompt_preview}")
            logger.debug(f"=== 完整 Prompt ({len(prompt)}字符) ===\n{prompt}\n=== End Prompt ===")

            # 设置生成配置（从配置文件读取温度参数）
            config = get_config()
            generation_config = {
                "temperature": config.gemini_temperature,
                "max_output_tokens": 8192,
            }

            # 检查缓存（避免重复分析相同股票 + 相同日期）
            cache: LLMResponseCache = get_llm_cache()
            cached_response = cache.get(code, prompt, model_name)

            if cached_response:
                logger.info(f"[{code}] 命中 LLM 缓存，跳过 API 调用")
                response_text = cached_response
                api_provider = "Cache"
                elapsed = 0.0
            else:
                # 记录实际使用的 API 提供方
                api_provider = (
                    "OpenAI" if self._use_openai
                    else "Anthropic" if self._use_anthropic
                    else "Gemini"
                )
                logger.info(f"[LLM 调用] 开始调用 {api_provider} API...")

                # 使用带重试的 API 调用
                start_time = time.time()
                response_text = self._call_api_with_retry(prompt, generation_config)
                elapsed = time.time() - start_time

                # 记录响应信息
                logger.info(f"[LLM 返回] {api_provider} API 响应成功，耗时 {elapsed:.2f}s, 响应长度 {len(response_text)} 字符")

                # 缓存响应
                cache.set(code, prompt, model_name, response_text)
                logger.debug(f"[{code}] 已缓存 LLM 响应")
            logger.info(f"[LLM返回] {api_provider} API 响应成功, 耗时 {elapsed:.2f}s, 响应长度 {len(response_text)} 字符")
            
            # 记录响应预览（INFO级别）和完整响应（DEBUG级别）
            response_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text
            logger.info(f"[LLM返回 预览]\n{response_preview}")
            logger.debug(f"=== {api_provider} 完整响应 ({len(response_text)}字符) ===\n{response_text}\n=== End Response ===")
            
            # 解析响应
            result = self._parse_response(response_text, code, name)
            result.raw_response = response_text
            result.search_performed = bool(news_context)
            result.market_snapshot = self._build_market_snapshot(context)

            logger.info(f"[LLM解析] {name}({code}) 分析完成: {result.trend_prediction}, 评分 {result.sentiment_score}")
            
            return result
            
        except Exception as e:
            logger.error(f"AI 分析 {name}({code}) 失败: {e}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary=f'分析过程出错: {str(e)[:100]}',
                risk_warning='分析失败，请稍后重试或手动分析',
                success=False,
                error_message=str(e),
            )
    
    def _format_prompt(
        self, 
        context: Dict[str, Any], 
        name: str,
        news_context: Optional[str] = None
    ) -> str:
        """
        格式化分析提示词（决策仪表盘 v2.0）
        
        包含：技术指标、实时行情（量比/换手率）、筹码分布、趋势分析、新闻
        
        Args:
            context: 技术面数据上下文（包含增强数据）
            name: 股票名称（默认值，可能被上下文覆盖）
            news_context: 预先搜索的新闻内容
        """
        code = context.get('code', 'Unknown')
        
        # 优先使用上下文中的股票名称（从 realtime_quote 获取）
        stock_name = context.get('stock_name', name)
        if not stock_name or stock_name == f'股票{code}':
            stock_name = STOCK_NAME_MAP.get(code, f'股票{code}')

        compact_news_context = self._compact_news_context(news_context)
        trend = context.get('trend_analysis') or {}
        signal_reasons = self._compact_prompt_items(trend.get('signal_reasons'))
        risk_factors = self._compact_prompt_items(trend.get('risk_factors'))

        today = context.get('today', {})
        
        # ========== 构建决策仪表盘格式的输入 ==========
        prompt = f"""# 决策仪表盘分析请求

## 股票基础信息
- 股票代码: {code}
- 股票名称: {stock_name}
- 分析日期: {context.get('date', '未知')}

## 技术面数据
### 今日行情
- 收盘价: {today.get('close', 'N/A')} 元
- 开盘价: {today.get('open', 'N/A')} 元
- 最高价: {today.get('high', 'N/A')} 元
- 最低价: {today.get('low', 'N/A')} 元
- 涨跌幅: {today.get('pct_chg', 'N/A')}%
- 成交量: {self._format_volume(today.get('volume'))}
- 成交额: {self._format_amount(today.get('amount'))}

### 均线系统
- MA5: {today.get('ma5', 'N/A')}
- MA10: {today.get('ma10', 'N/A')}
- MA20: {today.get('ma20', 'N/A')}
- 均线形态: {context.get('ma_status', '未知')}
"""
        
        # 添加实时行情数据（量比、换手率等）
        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""
### 实时行情增强数据
- 当前价格: {rt.get('price', 'N/A')} 元
- 量比: {rt.get('volume_ratio', 'N/A')} ({rt.get('volume_ratio_desc', '')})
- 换手率: {rt.get('turnover_rate', 'N/A')}%
- 市盈率(动态): {rt.get('pe_ratio', 'N/A')}
- 市净率: {rt.get('pb_ratio', 'N/A')}
- 总市值: {self._format_amount(rt.get('total_mv'))}
- 流通市值: {self._format_amount(rt.get('circ_mv'))}
- 60日涨跌幅: {rt.get('change_60d', 'N/A')}%
"""
        
        # 添加筹码分布数据
        if 'chip' in context:
            chip = context['chip']
            profit_ratio = chip.get('profit_ratio', 0)
            prompt += f"""
### 筹码分布数据
- 获利比例: {profit_ratio:.1%} (70-90%时警惕)
- 平均成本: {chip.get('avg_cost', 'N/A')} 元
- 90%筹码集中度: {chip.get('concentration_90', 0):.2%} (<15%为集中)
- 70%筹码集中度: {chip.get('concentration_70', 0):.2%}
- 筹码状态: {chip.get('chip_status', '未知')}
"""
        
        # 添加资金流向数据
        if 'fund_flow' in context:
            ff = context['fund_flow']
            prompt += f"""
### 资金流向与主力意图
- 当日资金状态: {ff.get('status', '未知')}
- 主力总净流入: {self._format_amount(ff.get('main_net_inflow', 0))} (占比: {self._format_percent(ff.get('main_net_inflow_ratio', 0)*100)})
- 超大单净额: {self._format_amount(ff.get('super_large_inflow', 0))}
- 大单净额: {self._format_amount(ff.get('large_inflow', 0))}
"""
        
        # 添加龙虎榜数据
        if 'dragon_tiger' in context and context['dragon_tiger'] is not None:
            dt = context['dragon_tiger']
            prompt += f"""
### 近期游资与龙虎榜热度
- 上榜日期: {dt.get('date', '未知')}
- 上榜原因: {dt.get('reason', '未知')}
- 净买入额: {dt.get('net_buy', 0) / 10000:.1f} 万
- 龙虎榜总买入: {dt.get('buy_amount', 0) / 10000:.1f} 万
- 龙虎榜总卖出: {dt.get('sell_amount', 0) / 10000:.1f} 万
"""

        # 添加板块轮动数据
        if 'sector_rotation' in context and context['sector_rotation'] is not None:
            sr = context['sector_rotation']
            prompt += f"""
### 所属板块综合表现
- 板块名称: {sr.get('industry', '未知')}
- 当日板块涨跌幅: {sr.get('change_pct', 0.0):+.2f}%
- 板块领涨股票: {sr.get('leader', '未知')}
- 板块涨平跌排名: {sr.get('rank', '未知')} / {sr.get('total_ranks', '未知')}
"""
        
        # 添加趋势分析结果（基于交易理念的预判）
        if trend:
            bias_warning = "🚨 超过5%，严禁追高！" if trend.get('bias_ma5', 0) > 5 else "✅ 安全范围"
            prompt += f"""
### 趋势分析预判
- 趋势状态: {trend.get('trend_status', '未知')}
- 均线排列: {trend.get('ma_alignment', '未知')} (MA5>MA10>MA20为多头)
- 趋势强度: {trend.get('trend_strength', 0)}/100
- 乖离率(MA5): {trend.get('bias_ma5', 0):+.2f}% ({bias_warning})
- 乖离率(MA10): {trend.get('bias_ma10', 0):+.2f}%
- 量能状态: {trend.get('volume_status', '未知')} {trend.get('volume_trend', '')}
- MACD 指标: {trend.get('macd_signal', '未知')}
- RSI 指标: {trend.get('rsi_signal', '未知')}
- BOLL 形态: {trend.get('boll_signal', '未知')}
- KDJ 指标: {trend.get('kdj_signal', '未知')}
- 系统信号: {trend.get('buy_signal', '未知')}
- 系统评分: {trend.get('signal_score', 0)}/100

#### 系统分析理由
**买入理由**:
{chr(10).join('- ' + r for r in signal_reasons) if signal_reasons else '- 无'}

**风险因素**:
{chr(10).join('- ' + r for r in risk_factors) if risk_factors else '- 无'}
"""
        
        # 添加昨日对比数据
        if 'yesterday' in context:
            volume_change = context.get('volume_change_ratio', 'N/A')
            prompt += f"""
### 量价变化
- 成交量较昨日变化：{volume_change}倍
- 价格较昨日变化：{context.get('price_change_ratio', 'N/A')}%
"""
        
        # 添加新闻搜索结果（重点区域）
        prompt += """
---

## 📰 舆情情报
"""
        if compact_news_context:
            prompt += f"""
以下是 **{stock_name}({code})** 近7日的新闻搜索结果，请重点提取：
1. 🚨 **风险警报**：减持、处罚、利空
2. 🎯 **利好催化**：业绩、合同、政策
3. 📊 **业绩预期**：年报预告、业绩快报

```
{compact_news_context}
```
"""
        else:
            prompt += """
未搜索到该股票近期的相关新闻。请主要依据技术面数据进行分析。
"""

        # 注入缺失数据警告
        if context.get('data_missing'):
            prompt += """
⚠️ **数据缺失警告**
由于接口限制，当前无法获取完整的实时行情和技术指标数据。
请 **忽略上述表格中的 N/A 数据**，重点依据 **【📰 舆情情报】** 中的新闻进行基本面和情绪面分析。
在回答技术面问题（如均线、乖离率）时，请直接说明“数据缺失，无法判断”，**严禁编造数据**。
"""

        # 明确的输出要求
        prompt += f"""
---

## ✅ 分析任务

请为 **{stock_name}({code})** 生成【决策仪表盘】，严格按照 JSON 格式输出。
"""
        if context.get('is_index_etf'):
            prompt += """
> ⚠️ **指数/ETF 分析约束**：该标的为指数跟踪型 ETF 或市场指数。
> - 风险分析仅关注：**指数走势、跟踪误差、市场流动性**
> - 严禁将基金公司的诉讼、声誉、高管变动纳入风险警报
> - 业绩预期基于**指数成分股整体表现**，而非基金公司财报
> - `risk_alerts` 中不得出现基金管理人相关的公司经营风险

"""
        prompt += f"""
### ⚠️ 重要：股票名称确认
如果上方显示的股票名称为"股票{code}"或不正确，请在分析开头**明确输出该股票的正确中文全称**。

### 重点关注（必须明确回答）：
1. ❓ 是否满足 MA5>MA10>MA20 多头排列？
2. ❓ 当前乖离率是否在安全范围内（<5%）？—— 超过5%必须标注"严禁追高"
3. ❓ 量能是否配合（缩量回调/放量突破）？
4. ❓ 筹码结构是否健康？
5. ❓ 消息面有无重大利空？（减持、处罚、业绩变脸等）

### 决策仪表盘要求：
- **股票名称**：必须输出正确的中文全称（如"贵州茅台"而非"股票600519"）
- **核心结论**：一句话说清该买/该卖/该等
- **持仓分类建议**：空仓者怎么做 vs 持仓者怎么做
- **具体狙击点位**：买入价、止损价、目标价（精确到分）
- **检查清单**：每项用 ✅/⚠️/❌ 标记

请输出完整的 JSON 格式决策仪表盘。"""
        
        return prompt

    def _compact_prompt_items(self, items: Optional[List[str]]) -> List[str]:
        """Clip long bullet lists before they enter the LLM prompt."""
        if not items:
            return []

        compact_items: List[str] = []
        for item in items[:self._MAX_PROMPT_BULLET_ITEMS]:
            text = str(item or '').strip()
            if not text:
                continue
            compact_items.append(_clip_text(text, self._MAX_PROMPT_ITEM_CHARS))
        return compact_items

    def _compact_news_context(self, news_context: Optional[str]) -> Optional[str]:
        """增强版：只保留关键信息（利空/利好/业绩），减少 prompt token 使用"""
        if not news_context:
            return news_context

        # 1. 先提取关键句子（包含关键词）- 优先保留
        key_phrases = [
            '减持', '处罚', '利空', '调查', '监管', '立案', '警示',  # 风险类
            '业绩', '预增', '预盈', '扭亏', '快报', '分红', '高送转',  # 业绩类
            '合同', '中标', '订单', '合作', '签约', '大单',  # 利好类
            '政策', '补贴', '扶持', '准入', '牌照',  # 政策类
            '重组', '并购', '回购', '增持', '举牌'  # 资本运作类
        ]

        important_lines = []
        other_lines = []

        for line in str(news_context).splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 检查是否包含关键词
            if any(phrase in line_stripped for phrase in key_phrases):
                important_lines.append(line_stripped)
            else:
                other_lines.append(line_stripped)

        # 2. 优先保留重要信息（最多 8 条）
        compact_lines = []
        for line in important_lines[:8]:
            compact_lines.append(_clip_text(line, 80))

        # 3. 补充其他信息（填充剩余配额）
        remaining = self._MAX_PROMPT_NEWS_LINES - len(compact_lines)
        for line in other_lines[:remaining]:
            compact_lines.append(_clip_text(line, 80))

        if not compact_lines:
            # 如果没有关键信息，返回原始压缩结果
            compact_lines = []
            for raw_line in str(news_context).splitlines():
                line = raw_line.rstrip()
                if not line.strip():
                    continue
                compact_lines.append(_clip_text(line.strip(), 80))
                if len(compact_lines) >= self._MAX_PROMPT_NEWS_LINES:
                    break

        compact_text = '\n'.join(compact_lines)
        return _clip_text(compact_text, self._MAX_PROMPT_NEWS_CHARS)

    def _format_volume(self, volume: Optional[float]) -> str:
        """格式化成交量显示"""
        if volume is None:
            return 'N/A'
        if volume >= 1e8:
            return f"{volume / 1e8:.2f} 亿股"
        elif volume >= 1e4:
            return f"{volume / 1e4:.2f} 万股"
        else:
            return f"{volume:.0f} 股"
    
    def _format_amount(self, amount: Optional[float]) -> str:
        """格式化成交额显示"""
        if amount is None:
            return 'N/A'
        if amount >= 1e8:
            return f"{amount / 1e8:.2f} 亿元"
        elif amount >= 1e4:
            return f"{amount / 1e4:.2f} 万元"
        else:
            return f"{amount:.0f} 元"

    def _format_percent(self, value: Optional[float]) -> str:
        """格式化百分比显示"""
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return 'N/A'

    def _format_price(self, value: Optional[float]) -> str:
        """格式化价格显示"""
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return 'N/A'

    def _build_market_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建当日行情快照（展示用）"""
        today = context.get('today', {}) or {}
        realtime = context.get('realtime', {}) or {}
        yesterday = context.get('yesterday', {}) or {}

        prev_close = yesterday.get('close')
        close = today.get('close')
        high = today.get('high')
        low = today.get('low')

        amplitude = None
        change_amount = None
        if prev_close not in (None, 0) and high is not None and low is not None:
            try:
                amplitude = (float(high) - float(low)) / float(prev_close) * 100
            except (TypeError, ValueError, ZeroDivisionError):
                amplitude = None
        if prev_close is not None and close is not None:
            try:
                change_amount = float(close) - float(prev_close)
            except (TypeError, ValueError):
                change_amount = None

        snapshot = {
            "date": context.get('date', '未知'),
            "close": self._format_price(close),
            "open": self._format_price(today.get('open')),
            "high": self._format_price(high),
            "low": self._format_price(low),
            "prev_close": self._format_price(prev_close),
            "pct_chg": self._format_percent(today.get('pct_chg')),
            "change_amount": self._format_price(change_amount),
            "amplitude": self._format_percent(amplitude),
            "volume": self._format_volume(today.get('volume')),
            "amount": self._format_amount(today.get('amount')),
        }

        if realtime:
            snapshot.update({
                "price": self._format_price(realtime.get('price')),
                "volume_ratio": realtime.get('volume_ratio', 'N/A'),
                "turnover_rate": self._format_percent(realtime.get('turnover_rate')),
                "source": getattr(realtime.get('source'), 'value', realtime.get('source', 'N/A')),
            })

        return snapshot

    def _parse_response(
        self, 
        response_text: str, 
        code: str, 
        name: str
    ) -> AnalysisResult:
        """
        解析 Gemini 响应（决策仪表盘版）
        
        尝试从响应中提取 JSON 格式的分析结果，包含 dashboard 字段
        如果解析失败，尝试智能提取或返回默认结果
        """
        return parse_response(response_text, code, name, AnalysisResult)
    
    def _fix_json_string(self, json_str: str) -> str:
        """修复常见的 JSON 格式问题"""
        return fix_json_string(json_str)
    
    def _parse_text_response(
        self, 
        response_text: str, 
        code: str, 
        name: str
    ) -> AnalysisResult:
        """从纯文本响应中尽可能提取分析信息"""
        return parse_text_response(response_text, code, name, AnalysisResult)
    
    def batch_analyze(
        self, 
        contexts: List[Dict[str, Any]],
        delay_between: float = 2.0
    ) -> List[AnalysisResult]:
        """
        批量分析多只股票
        
        注意：为避免 API 速率限制，每次分析之间会有延迟
        
        Args:
            contexts: 上下文数据列表
            delay_between: 每次分析之间的延迟（秒）
            
        Returns:
            AnalysisResult 列表
        """
        results = []
        
        for i, context in enumerate(contexts):
            if i > 0:
                logger.debug(f"等待 {delay_between} 秒后继续...")
                time.sleep(delay_between)
            
            result = self.analyze(context)
            results.append(result)
        
        return results


# 便捷函数
def get_analyzer() -> GeminiAnalyzer:
    """获取 LLM 分析器实例"""
    return GeminiAnalyzer()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    # 模拟上下文数据
    test_context = {
        'code': '600519',
        'date': '2026-01-09',
        'today': {
            'open': 1800.0,
            'high': 1850.0,
            'low': 1780.0,
            'close': 1820.0,
            'volume': 10000000,
            'amount': 18200000000,
            'pct_chg': 1.5,
            'ma5': 1810.0,
            'ma10': 1800.0,
            'ma20': 1790.0,
            'volume_ratio': 1.2,
        },
        'ma_status': '多头排列 📈',
        'volume_change_ratio': 1.3,
        'price_change_ratio': 1.5,
    }
    
    analyzer = GeminiAnalyzer()
    
    if analyzer.is_available():
        print("=== AI 分析测试 ===")
        result = analyzer.analyze(test_context)
        print(f"分析结果: {result.to_dict()}")
    else:
        print("Gemini API 未配置，跳过测试")
