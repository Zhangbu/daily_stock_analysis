# -*- coding: utf-8 -*-
"""
Agent Executor — ReAct loop with tool calling.

Orchestrates the LLM + tools interaction loop:
1. Build system prompt (persona + tools + skills)
2. Send to LLM with tool declarations
3. If tool_call → execute tool → feed result back
4. If text → parse as final answer
5. Loop until final answer or max_steps

Optimizations:
- TTL-based tool result caching
- Tool execution retry with exponential backoff
- Streaming progress callbacks
- Structured tool call tracing
- Async execution support
"""

import asyncio
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from json_repair import repair_json

from src.agent.llm_adapter import LLMToolAdapter
from src.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================
# Tool execution retry configuration
# ============================================================

# Maximum retries for failed tool execution
TOOL_MAX_RETRIES: int = 2

# Base delay for exponential backoff (seconds)
TOOL_RETRY_BASE_DELAY: float = 0.5

# Maximum delay between retries (seconds)
TOOL_RETRY_MAX_DELAY: float = 5.0


# Tool name → short label used to build contextual thinking messages
_THINKING_TOOL_LABELS: Dict[str, str] = {
    "get_realtime_quote": "行情获取",
    "get_daily_history": "K线数据获取",
    "analyze_trend": "技术指标分析",
    "get_chip_distribution": "筹码分布分析",
    "search_stock_news": "新闻搜索",
    "search_comprehensive_intel": "综合情报搜索",
    "get_market_indices": "市场概览获取",
    "get_sector_rankings": "行业板块分析",
    "get_analysis_context": "历史分析上下文",
    "get_stock_info": "基本信息获取",
    "analyze_pattern": "K线形态识别",
    "get_volume_analysis": "量能分析",
    "calculate_ma": "均线计算",
}


# ============================================================
# Agent result
# ============================================================

@dataclass
class ToolCallRecord:
    """Detailed record of a single tool call execution."""
    step: int
    tool: str
    arguments: Dict[str, Any]
    success: bool
    duration: float
    result_length: int
    cached: bool = False
    retries: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "arguments": self.arguments,
            "success": self.success,
            "duration": self.duration,
            "result_length": self.result_length,
            "cached": self.cached,
            "retries": self.retries,
            "error": self.error,
        }


@dataclass
class AgentResult:
    """Result from an agent execution run."""
    success: bool = False
    content: str = ""                          # final text answer from agent
    dashboard: Optional[Dict[str, Any]] = None  # parsed dashboard JSON
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)  # execution trace
    total_steps: int = 0
    total_tokens: int = 0
    provider: str = ""
    error: Optional[str] = None
    # Enhanced metrics
    total_tool_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    total_retries: int = 0

    def get_performance_summary(self) -> str:
        """Generate a human-readable performance summary."""
        parts = [
            f"Steps: {self.total_steps}",
            f"Tokens: {self.total_tokens}",
            f"Tool time: {self.total_tool_time:.2f}s",
        ]
        if self.cache_hits + self.cache_misses > 0:
            hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
            parts.append(f"Cache: {self.cache_hits}/{self.cache_hits + self.cache_misses} ({hit_rate:.0f}%)")
        if self.total_retries > 0:
            parts.append(f"Retries: {self.total_retries}")
        return " | ".join(parts)


# ============================================================
# System prompt builder
# ============================================================

AGENT_SYSTEM_PROMPT = """你是一位趋势交易股票分析 Agent，必须使用工具获取真实数据，并输出严格合法的【决策仪表盘】JSON。

流程：
- Stage 1: `get_realtime_quote` + `get_daily_history`
- Stage 2: `analyze_trend` + `get_chip_distribution`
- Stage 3: `search_stock_news`
- Stage 4: 基于已拿到的数据生成最终 JSON
- 不得跨阶段混合调用；若已具备实时行情、20日以上K线、趋势、筹码、新闻，就直接生成报告。

交易原则：
- 优先多头排列：MA5 > MA10 > MA20；空头或跌破 MA20 时优先观望/减仓/卖出。
- 乖离率 < 2% 最优，2-5% 可谨慎参与，> 5% 视为追高风险。
- 缩量回踩支撑、放量突破、筹码集中且获利盘不过热时可提高评分。
- 风险排查至少覆盖：减持、业绩恶化、监管处罚、政策利空、解禁、估值过高。
- 强势趋势股可适度放宽乖离率，但必须给出止损和仓位控制。

规则：
- 只用工具返回的数据，禁止编造。
- 失败工具记录原因后跳过，不要对同一失败反复重试。
- 结合已激活策略输出判断。
- 最终答案只能是 JSON，不要 Markdown、代码块或额外解释。

{skills_section}

JSON 合约：
- 顶层字段必须包含：stock_name, sentiment_score, trend_prediction, operation_advice, decision_type, confidence_level, dashboard, analysis_summary, key_points, risk_warning, buy_reason, trend_analysis, short_term_outlook, medium_term_outlook, technical_analysis, ma_analysis, volume_analysis, pattern_analysis, fundamental_analysis, sector_position, company_highlights, news_summary, market_sentiment, hot_topics。
- `dashboard.core_conclusion` 必须包含：one_sentence, signal_type, time_sensitivity, position_advice(no_position, has_position)。
- `dashboard.data_perspective` 必须包含：trend_status, price_position, volume_analysis, chip_structure。
- `dashboard.intelligence` 必须包含：latest_news, risk_alerts, positive_catalysts, earnings_outlook, sentiment_summary。
- `dashboard.battle_plan` 必须包含：sniper_points, position_strategy, action_checklist。
- `decision_type` 只能是 buy/hold/sell；`operation_advice` 只能是 买入/加仓/持有/减仓/卖出/观望；`confidence_level` 只能是 高/中/低。
- `signal_type` 只能是“🟢买入信号/🟡持有观望/🔴卖出信号/⚠️风险警告”之一。
- `risk_alerts`、`positive_catalysts` 返回数组；无内容时用空数组。
- `action_checklist` 每项必须以 ✅/⚠️/❌ 开头。
- 能给价格时尽量给出买点、止损、止盈、支撑、压力的具体数值。
- 股票名称必须输出正确中文名；若数据缺失，明确写“数据缺失，无法判断”。

输出前自检：JSON 合法、字段齐全、结论与风险一致、没有编造数据。"""

CHAT_SYSTEM_PROMPT = """你是一位趋势交易股票分析 Agent，负责回答用户的股票问题。

当问题涉及具体股票分析时，按顺序使用工具：
- Stage 1: `get_realtime_quote` + `get_daily_history`
- Stage 2: `analyze_trend` + `get_chip_distribution`
- Stage 3: `search_stock_news`
- Stage 4: 基于真实数据给出结论
- 不得跨阶段混合调用；若核心数据已齐，可停止继续查数。

回答规则：
- 只基于工具结果作答，禁止编造。
- 结合已激活策略说明判断。
- 优先趋势交易：多头排列优于震荡，震荡优于空头；乖离率 > 5% 视为追高风险。
- 风险排查至少覆盖减持、业绩恶化、监管处罚、政策利空、解禁、估值过高。
- 工具失败时说明局限，基于已有数据继续，不要反复重试同一失败。
- 这是自由对话场景，直接用自然语言回答，不需要输出 JSON。

{skills_section}"""


# ============================================================
# Agent Executor
# ============================================================

class AgentExecutor:
    """ReAct agent loop with tool calling.

    Features:
    - TTL-based tool result caching
    - Tool execution retry with exponential backoff
    - Streaming progress callbacks
    - Structured tool call tracing
    - Async execution support
    - Smart context reuse hints

    Usage::

        executor = AgentExecutor(tool_registry, llm_adapter)
        result = executor.run("Analyze stock 600519")
        
        # With progress callback
        result = executor.run("Analyze 600519", progress_callback=lambda e: print(e))
        
        # Async execution
        result = await executor.run_async("Analyze 600519")
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
        max_steps: int = 10,
        use_cache: bool = True,
        max_retries: int = TOOL_MAX_RETRIES,
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions
        self.max_steps = max_steps
        self.use_cache = use_cache
        self.max_retries = max_retries

    # ============================================================
    # Tool execution with retry and caching
    # ============================================================

    def _execute_tool_with_retry(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        use_cache: bool = True,
    ) -> Tuple[Any, bool, int, Optional[str]]:
        """Execute a tool with retry logic and optional caching.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            use_cache: Whether to use caching.

        Returns:
            Tuple of (result, success, retry_count, error_message).
        """
        last_error: Optional[str] = None
        retry_count = 0

        for attempt in range(self.max_retries + 1):
            try:
                if use_cache and self.use_cache:
                    result, metadata = self.tool_registry.execute_with_cache(
                        tool_name, use_cache=True, **arguments
                    )
                else:
                    result = self.tool_registry.execute(tool_name, **arguments)
                    metadata = {}
                return result, True, retry_count, None
            except Exception as e:
                last_error = str(e)
                retry_count = attempt
                if attempt < self.max_retries:
                    # Exponential backoff
                    delay = min(TOOL_RETRY_BASE_DELAY * (2 ** attempt), TOOL_RETRY_MAX_DELAY)
                    logger.warning(
                        f"Tool '{tool_name}' failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

        return {"error": last_error}, False, retry_count, last_error

    async def _execute_tool_with_retry_async(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        use_cache: bool = True,
    ) -> Tuple[Any, bool, int, Optional[str]]:
        """Execute a tool asynchronously with retry logic and caching."""
        last_error: Optional[str] = None
        retry_count = 0

        for attempt in range(self.max_retries + 1):
            try:
                if use_cache and self.use_cache:
                    result, metadata = await self.tool_registry.execute_async_with_cache(
                        tool_name, use_cache=True, **arguments
                    )
                else:
                    result = await self.tool_registry.execute_async(tool_name, **arguments)
                    metadata = {}
                return result, True, retry_count, None
            except Exception as e:
                last_error = str(e)
                retry_count = attempt
                if attempt < self.max_retries:
                    delay = min(TOOL_RETRY_BASE_DELAY * (2 ** attempt), TOOL_RETRY_MAX_DELAY)
                    logger.warning(
                        f"Tool '{tool_name}' failed async (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

        return {"error": last_error}, False, retry_count, last_error

    # ============================================================
    # Enhanced user message builder with context reuse hints
    # ============================================================

    def _build_context_reuse_hint(self, context: Optional[Dict[str, Any]]) -> str:
        """Build a compact hint for pre-fetched context data."""
        if not context:
            return ""

        available_data = []
        if context.get("realtime_quote"):
            available_data.append("实时行情")
        if context.get("chip_distribution"):
            available_data.append("筹码分布")
        if context.get("daily_history"):
            available_data.append("历史K线")
        if context.get("trend_analysis"):
            available_data.append("趋势指标")
        if context.get("stock_info"):
            available_data.append("股票信息")
        if context.get("news"):
            available_data.append("新闻")

        if not available_data:
            return ""

        return "\n\n系统已预取：" + "、".join(available_data) + "。请优先复用，仅补充缺失数据。"

    # ============================================================
    # Synchronous execution
    # ============================================================

    def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentResult:
        """Execute the agent loop for a given task.

        Args:
            task: The user task / analysis request.
            context: Optional context dict (e.g., {"stock_code": "600519"}).

        Returns:
            AgentResult with parsed dashboard or error.
        """
        start_time = time.time()
        tool_calls_log: List[Dict[str, Any]] = []
        total_tokens = 0

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## 激活的交易策略\n\n{self.skill_instructions}"
        system_prompt = AGENT_SYSTEM_PROMPT.format(skills_section=skills_section)

        # Build tool declarations for all providers
        tool_decls = {
            "gemini": self.tool_registry.to_gemini_declarations(),
            "openai": self.tool_registry.to_openai_tools(),
            "anthropic": self.tool_registry.to_anthropic_tools(),
        }

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_message(task, context)},
        ]

        return self._run_loop(messages, tool_decls, start_time, tool_calls_log, total_tokens, parse_dashboard=True)

    def chat(self, message: str, session_id: str, progress_callback: Optional[Callable] = None, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a free-form chat message.

        Args:
            message: The user's chat message.
            session_id: The conversation session ID.
            progress_callback: Optional callback for streaming progress events.
            context: Optional context dict from previous analysis for data reuse.

        Returns:
            AgentResult with the text response.
        """
        from src.agent.conversation import conversation_manager
        
        start_time = time.time()
        tool_calls_log: List[Dict[str, Any]] = []
        total_tokens = 0

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## 激活的交易策略\n\n{self.skill_instructions}"
        system_prompt = CHAT_SYSTEM_PROMPT.format(skills_section=skills_section)

        # Build tool declarations for all providers
        tool_decls = {
            "gemini": self.tool_registry.to_gemini_declarations(),
            "openai": self.tool_registry.to_openai_tools(),
            "anthropic": self.tool_registry.to_anthropic_tools(),
        }

        # Get conversation history
        session = conversation_manager.get_or_create(session_id)
        history = session.get_history()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)

        # Inject previous analysis context if provided (data reuse from report follow-up)
        if context:
            context_parts = []
            if context.get("stock_code"):
                context_parts.append(f"股票代码: {context['stock_code']}")
            if context.get("stock_name"):
                context_parts.append(f"股票名称: {context['stock_name']}")
            if context.get("previous_price"):
                context_parts.append(f"上次分析价格: {context['previous_price']}")
            if context.get("previous_change_pct"):
                context_parts.append(f"上次涨跌幅: {context['previous_change_pct']}%")
            if context.get("previous_analysis_summary"):
                summary = context["previous_analysis_summary"]
                summary_text = json.dumps(summary, ensure_ascii=False) if isinstance(summary, dict) else str(summary)
                context_parts.append(f"上次分析摘要:\n{summary_text}")
            if context.get("previous_strategy"):
                strategy = context["previous_strategy"]
                strategy_text = json.dumps(strategy, ensure_ascii=False) if isinstance(strategy, dict) else str(strategy)
                context_parts.append(f"上次策略分析:\n{strategy_text}")
            if context_parts:
                context_msg = "[系统提供的历史分析上下文，可供参考对比]\n" + "\n".join(context_parts)
                messages.append({"role": "user", "content": context_msg})
                messages.append({"role": "assistant", "content": "好的，我已了解该股票的历史分析数据。请告诉我你想了解什么？"})

        messages.append({"role": "user", "content": message})

        # Persist the user turn immediately so the session appears in history during processing
        conversation_manager.add_message(session_id, "user", message)

        result = self._run_loop(messages, tool_decls, start_time, tool_calls_log, total_tokens, parse_dashboard=False, progress_callback=progress_callback)

        # Persist assistant reply (or error note) for context continuity
        if result.success:
            conversation_manager.add_message(session_id, "assistant", result.content)
        else:
            error_note = f"[分析失败] {result.error or '未知错误'}"
            conversation_manager.add_message(session_id, "assistant", error_note)

        return result

    def _run_loop(self, messages: List[Dict[str, Any]], tool_decls: Dict[str, Any], start_time: float, tool_calls_log: List[Dict[str, Any]], total_tokens: int, parse_dashboard: bool, progress_callback: Optional[Callable] = None) -> AgentResult:
        provider_used = ""

        for step in range(self.max_steps):
            logger.info(f"Agent step {step + 1}/{self.max_steps}")

            if progress_callback:
                if not tool_calls_log:
                    thinking_msg = "正在制定分析路径..."
                else:
                    last_tool = tool_calls_log[-1].get("tool", "")
                    label = _THINKING_TOOL_LABELS.get(last_tool, last_tool)
                    thinking_msg = f"「{label}」已完成，继续深入分析..."
                progress_callback({"type": "thinking", "step": step + 1, "message": thinking_msg})

            response = self.llm_adapter.call_with_tools(messages, tool_decls)
            provider_used = response.provider
            total_tokens += response.usage.get("total_tokens", 0)

            if response.tool_calls:
                # LLM wants to call tools
                logger.info(f"Agent requesting {len(response.tool_calls)} tool call(s): "
                          f"{[tc.name for tc in response.tool_calls]}")

                # Add assistant message with tool calls to history
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.name,
                            "arguments": tc.arguments,
                            **({"thought_signature": tc.thought_signature} if tc.thought_signature is not None else {}),
                        }
                        for tc in response.tool_calls
                    ],
                }
                # Only present for DeepSeek thinking mode; None for all other providers
                if response.reasoning_content is not None:
                    assistant_msg["reasoning_content"] = response.reasoning_content
                messages.append(assistant_msg)

                # Execute tool calls — parallel when multiple, sequential when single
                tool_results: List[Dict[str, Any]] = []

                def _exec_single_tool(tc_item):
                    """Execute one tool and return (tc, result_str, success, duration)."""
                    t0 = time.time()
                    try:
                        res = self.tool_registry.execute(tc_item.name, **tc_item.arguments)
                        res_str = self._serialize_tool_result(res)
                        ok = True
                    except Exception as e:
                        res_str = json.dumps({"error": str(e)})
                        ok = False
                        logger.warning(f"Tool '{tc_item.name}' failed: {e}")
                    dur = time.time() - t0
                    return tc_item, res_str, ok, round(dur, 2)

                if len(response.tool_calls) == 1:
                    # Single tool — run inline (no thread overhead)
                    tc = response.tool_calls[0]
                    if progress_callback:
                        progress_callback({"type": "tool_start", "step": step + 1, "tool": tc.name})
                    _, result_str, success, tool_duration = _exec_single_tool(tc)
                    if progress_callback:
                        progress_callback({"type": "tool_done", "step": step + 1, "tool": tc.name, "success": success, "duration": tool_duration})
                    tool_calls_log.append({
                        "step": step + 1, "tool": tc.name, "arguments": tc.arguments,
                        "success": success, "duration": tool_duration, "result_length": len(result_str),
                    })
                    tool_results.append({"tc": tc, "result_str": result_str})
                else:
                    # Multiple tools — run in parallel threads
                    for tc in response.tool_calls:
                        if progress_callback:
                            progress_callback({"type": "tool_start", "step": step + 1, "tool": tc.name})

                    with ThreadPoolExecutor(max_workers=min(len(response.tool_calls), 5)) as pool:
                        futures = {pool.submit(_exec_single_tool, tc): tc for tc in response.tool_calls}
                        for future in as_completed(futures):
                            tc_item, result_str, success, tool_duration = future.result()
                            if progress_callback:
                                progress_callback({"type": "tool_done", "step": step + 1, "tool": tc_item.name, "success": success, "duration": tool_duration})
                            tool_calls_log.append({
                                "step": step + 1, "tool": tc_item.name, "arguments": tc_item.arguments,
                                "success": success, "duration": tool_duration, "result_length": len(result_str),
                            })
                            tool_results.append({"tc": tc_item, "result_str": result_str})

                # Append tool results to messages (ordered by original tool_calls order)
                tc_order = {tc.id: i for i, tc in enumerate(response.tool_calls)}
                tool_results.sort(key=lambda x: tc_order.get(x["tc"].id, 0))
                for tr in tool_results:
                    messages.append({
                        "role": "tool",
                        "name": tr["tc"].name,
                        "tool_call_id": tr["tc"].id,
                        "content": tr["result_str"],
                    })

            else:
                # LLM returned text — this is the final answer
                logger.info(f"Agent completed in {step + 1} steps "
                          f"({time.time() - start_time:.1f}s, {total_tokens} tokens)")
                if progress_callback:
                    progress_callback({"type": "generating", "step": step + 1, "message": "正在生成最终分析..."})

                final_content = response.content or ""
                
                if parse_dashboard:
                    dashboard = self._parse_dashboard(final_content)
                    return AgentResult(
                        success=dashboard is not None,
                        content=final_content,
                        dashboard=dashboard,
                        tool_calls_log=tool_calls_log,
                        total_steps=step + 1,
                        total_tokens=total_tokens,
                        provider=provider_used,
                        error=None if dashboard else "Failed to parse dashboard JSON from agent response",
                    )
                else:
                    if response.provider == "error":
                        return AgentResult(
                            success=False,
                            content="",
                            dashboard=None,
                            tool_calls_log=tool_calls_log,
                            total_steps=step + 1,
                            total_tokens=total_tokens,
                            provider=provider_used,
                            error=final_content,
                        )
                    return AgentResult(
                        success=True,
                        content=final_content,
                        dashboard=None,
                        tool_calls_log=tool_calls_log,
                        total_steps=step + 1,
                        total_tokens=total_tokens,
                        provider=provider_used,
                        error=None,
                    )

        # Max steps exceeded
        logger.warning(f"Agent hit max steps ({self.max_steps})")
        return AgentResult(
            success=False,
            content="",
            tool_calls_log=tool_calls_log,
            total_steps=self.max_steps,
            total_tokens=total_tokens,
            provider=provider_used,
            error=f"Agent exceeded max steps ({self.max_steps})",
        )

    def _build_user_message(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the initial user message."""
        parts = [task]
        if context:
            if context.get("stock_code"):
                parts.append(f"股票代码: {context['stock_code']}")
            if context.get("report_type"):
                parts.append(f"报告类型: {context['report_type']}")

            realtime_summary = self._summarize_realtime_quote(context.get("realtime_quote"))
            if realtime_summary:
                parts.append(f"已知实时行情: {realtime_summary}")

            chip_summary = self._summarize_chip_distribution(context.get("chip_distribution"))
            if chip_summary:
                parts.append(f"已知筹码摘要: {chip_summary}")

        parts.append("请仅调用缺失工具，并输出决策仪表盘 JSON。")
        return "\n".join(parts)

    def _summarize_realtime_quote(self, quote: Optional[Dict[str, Any]]) -> str:
        """Summarize key realtime quote fields for the initial prompt."""
        if not quote:
            return ""

        fields = []
        for label, key, suffix in [
            ("价格", "price", ""),
            ("涨跌幅", "change_percent", "%"),
            ("量比", "volume_ratio", ""),
            ("换手率", "turnover_rate", "%"),
        ]:
            value = quote.get(key)
            if value in (None, "", "N/A"):
                continue
            fields.append(f"{label}{value}{suffix}")
        return "，".join(fields)

    def _summarize_chip_distribution(self, chip: Optional[Dict[str, Any]]) -> str:
        """Summarize key chip distribution fields for the initial prompt."""
        if not chip:
            return ""

        fields = []
        for label, key, suffix in [
            ("获利比例", "profit_ratio", ""),
            ("平均成本", "avg_cost", ""),
            ("90%集中度", "concentration_90", ""),
            ("筹码状态", "chip_status", ""),
        ]:
            value = chip.get(key)
            if value in (None, "", "N/A"):
                continue
            fields.append(f"{label}{value}{suffix}")
        return "，".join(fields)

    def _serialize_tool_result(self, result: Any) -> str:
        """Serialize a tool result to a JSON string for the LLM."""
        if result is None:
            return json.dumps({"result": None})
        if isinstance(result, str):
            return result
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                return str(result)
        # Dataclass or object with __dict__
        if hasattr(result, '__dict__'):
            try:
                d = {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
                return json.dumps(d, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                return str(result)
        return str(result)

    def _parse_dashboard(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract and parse the Decision Dashboard JSON from agent response."""
        if not content:
            return None

        # Try to extract JSON from markdown code blocks
        json_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_blocks:
            for block in json_blocks:
                try:
                    parsed = json.loads(block)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    try:
                        repaired = repair_json(block)
                        parsed = json.loads(repaired)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        continue

        # Try raw JSON parse
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try json_repair
        try:
            repaired = repair_json(content)
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Try to find JSON object in text
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            candidate = content[brace_start:brace_end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                try:
                    repaired = repair_json(candidate)
                    parsed = json.loads(repaired)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass

        logger.warning("Failed to parse dashboard JSON from agent response")
        return None

    # ============================================================
    # Async execution methods
    # ============================================================

    async def run_async(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentResult:
        """Execute the agent loop asynchronously.

        Args:
            task: The user task / analysis request.
            context: Optional context dict (e.g., {"stock_code": "600519"}).
            progress_callback: Optional callback for streaming progress events.

        Returns:
            AgentResult with parsed dashboard or error.
        """
        start_time = time.time()
        tool_calls_log: List[Dict[str, Any]] = []
        total_tokens = 0
        total_tool_time = 0.0
        cache_hits = 0
        cache_misses = 0
        total_retries = 0

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## 激活的交易策略\n\n{self.skill_instructions}"
        system_prompt = AGENT_SYSTEM_PROMPT.format(skills_section=skills_section)

        # Build tool declarations for all providers
        tool_decls = {
            "gemini": self.tool_registry.to_gemini_declarations(),
            "openai": self.tool_registry.to_openai_tools(),
            "anthropic": self.tool_registry.to_anthropic_tools(),
        }

        # Initialize conversation with context reuse hint
        user_message = self._build_user_message(task, context)
        context_hint = self._build_context_reuse_hint(context)
        if context_hint:
            user_message += context_hint

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        return await self._run_loop_async(
            messages, tool_decls, start_time, tool_calls_log, total_tokens,
            total_tool_time, cache_hits, cache_misses, total_retries,
            parse_dashboard=True, progress_callback=progress_callback
        )

    async def chat_async(
        self,
        message: str,
        session_id: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Execute the agent loop asynchronously for a free-form chat message.

        Args:
            message: The user's chat message.
            session_id: The conversation session ID.
            progress_callback: Optional callback for streaming progress events.
            context: Optional context dict from previous analysis for data reuse.

        Returns:
            AgentResult with the text response.
        """
        from src.agent.conversation import conversation_manager

        start_time = time.time()
        tool_calls_log: List[Dict[str, Any]] = []
        total_tokens = 0
        total_tool_time = 0.0
        cache_hits = 0
        cache_misses = 0
        total_retries = 0

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## 激活的交易策略\n\n{self.skill_instructions}"
        system_prompt = CHAT_SYSTEM_PROMPT.format(skills_section=skills_section)

        # Build tool declarations for all providers
        tool_decls = {
            "gemini": self.tool_registry.to_gemini_declarations(),
            "openai": self.tool_registry.to_openai_tools(),
            "anthropic": self.tool_registry.to_anthropic_tools(),
        }

        # Get conversation history
        session = conversation_manager.get_or_create(session_id)
        history = session.get_history()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)

        # Inject previous analysis context if provided
        if context:
            context_parts = []
            if context.get("stock_code"):
                context_parts.append(f"股票代码: {context['stock_code']}")
            if context.get("stock_name"):
                context_parts.append(f"股票名称: {context['stock_name']}")
            if context.get("previous_price"):
                context_parts.append(f"上次分析价格: {context['previous_price']}")
            if context.get("previous_change_pct"):
                context_parts.append(f"上次涨跌幅: {context['previous_change_pct']}%")
            if context.get("previous_analysis_summary"):
                summary = context["previous_analysis_summary"]
                summary_text = json.dumps(summary, ensure_ascii=False) if isinstance(summary, dict) else str(summary)
                context_parts.append(f"上次分析摘要:\n{summary_text}")
            if context_parts:
                context_msg = "[系统提供的历史分析上下文，可供参考对比]\n" + "\n".join(context_parts)
                messages.append({"role": "user", "content": context_msg})
                messages.append({"role": "assistant", "content": "好的，我已了解该股票的历史分析数据。请告诉我你想了解什么？"})

        # Add context reuse hint
        user_message = message
        context_hint = self._build_context_reuse_hint(context)
        if context_hint:
            user_message += context_hint

        messages.append({"role": "user", "content": user_message})

        # Persist the user turn
        conversation_manager.add_message(session_id, "user", message)

        result = await self._run_loop_async(
            messages, tool_decls, start_time, tool_calls_log, total_tokens,
            total_tool_time, cache_hits, cache_misses, total_retries,
            parse_dashboard=False, progress_callback=progress_callback
        )

        # Persist assistant reply
        if result.success:
            conversation_manager.add_message(session_id, "assistant", result.content)
        else:
            error_note = f"[分析失败] {result.error or '未知错误'}"
            conversation_manager.add_message(session_id, "assistant", error_note)

        return result

    async def _run_loop_async(
        self,
        messages: List[Dict[str, Any]],
        tool_decls: Dict[str, Any],
        start_time: float,
        tool_calls_log: List[Dict[str, Any]],
        total_tokens: int,
        total_tool_time: float,
        cache_hits: int,
        cache_misses: int,
        total_retries: int,
        parse_dashboard: bool,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentResult:
        """Async implementation of the ReAct loop with caching and retry."""
        provider_used = ""

        for step in range(self.max_steps):
            logger.info(f"Agent step {step + 1}/{self.max_steps} (async)")

            if progress_callback:
                if not tool_calls_log:
                    thinking_msg = "正在制定分析路径..."
                else:
                    last_tool = tool_calls_log[-1].get("tool", "")
                    label = _THINKING_TOOL_LABELS.get(last_tool, last_tool)
                    thinking_msg = f"「{label}」已完成，继续深入分析..."
                progress_callback({"type": "thinking", "step": step + 1, "message": thinking_msg})

            response = self.llm_adapter.call_with_tools(messages, tool_decls)
            provider_used = response.provider
            total_tokens += response.usage.get("total_tokens", 0)

            if response.tool_calls:
                logger.info(f"Agent requesting {len(response.tool_calls)} tool call(s): "
                          f"{[tc.name for tc in response.tool_calls]}")

                # Add assistant message with tool calls to history
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.name,
                            "arguments": tc.arguments,
                            **({"thought_signature": tc.thought_signature} if tc.thought_signature is not None else {}),
                        }
                        for tc in response.tool_calls
                    ],
                }
                if response.reasoning_content is not None:
                    assistant_msg["reasoning_content"] = response.reasoning_content
                messages.append(assistant_msg)

                # Execute tool calls asynchronously with caching and retry
                tool_results: List[Dict[str, Any]] = []

                async def _exec_single_tool_async(tc_item):
                    """Execute one tool async with retry and caching."""
                    t0 = time.time()
                    if progress_callback:
                        progress_callback({"type": "tool_start", "step": step + 1, "tool": tc_item.name})

                    result, success, retries, error = await self._execute_tool_with_retry_async(
                        tc_item.name, tc_item.arguments, use_cache=self.use_cache
                    )

                    duration = time.time() - t0
                    res_str = self._serialize_tool_result(result)

                    if progress_callback:
                        progress_callback({
                            "type": "tool_done",
                            "step": step + 1,
                            "tool": tc_item.name,
                            "success": success,
                            "duration": round(duration, 2),
                        })

                    return tc_item, res_str, success, round(duration, 2), retries

                # Execute all tools concurrently
                tasks = [_exec_single_tool_async(tc) for tc in response.tool_calls]
                results = await asyncio.gather(*tasks)

                for tc_item, result_str, success, tool_duration, retries in results:
                    total_retries += retries
                    total_tool_time += tool_duration

                    tool_calls_log.append({
                        "step": step + 1,
                        "tool": tc_item.name,
                        "arguments": tc_item.arguments,
                        "success": success,
                        "duration": tool_duration,
                        "result_length": len(result_str),
                        "retries": retries,
                    })
                    tool_results.append({"tc": tc_item, "result_str": result_str})

                # Append tool results to messages
                tc_order = {tc.id: i for i, tc in enumerate(response.tool_calls)}
                tool_results.sort(key=lambda x: tc_order.get(x["tc"].id, 0))
                for tr in tool_results:
                    messages.append({
                        "role": "tool",
                        "name": tr["tc"].name,
                        "tool_call_id": tr["tc"].id,
                        "content": tr["result_str"],
                    })

            else:
                # LLM returned text — final answer
                logger.info(f"Agent completed in {step + 1} steps "
                          f"({time.time() - start_time:.1f}s, {total_tokens} tokens)")
                if progress_callback:
                    progress_callback({"type": "generating", "step": step + 1, "message": "正在生成最终分析..."})

                final_content = response.content or ""

                # Get cache stats
                cache_stats = self.tool_registry.get_cache_stats()
                cache_hits = cache_stats.get("cache_hits", 0)
                cache_misses = cache_stats.get("cache_misses", 0)

                if parse_dashboard:
                    dashboard = self._parse_dashboard(final_content)
                    return AgentResult(
                        success=dashboard is not None,
                        content=final_content,
                        dashboard=dashboard,
                        tool_calls_log=tool_calls_log,
                        total_steps=step + 1,
                        total_tokens=total_tokens,
                        provider=provider_used,
                        error=None if dashboard else "Failed to parse dashboard JSON from agent response",
                        total_tool_time=total_tool_time,
                        cache_hits=cache_hits,
                        cache_misses=cache_misses,
                        total_retries=total_retries,
                    )
                else:
                    if response.provider == "error":
                        return AgentResult(
                            success=False,
                            content="",
                            dashboard=None,
                            tool_calls_log=tool_calls_log,
                            total_steps=step + 1,
                            total_tokens=total_tokens,
                            provider=provider_used,
                            error=final_content,
                            total_tool_time=total_tool_time,
                            cache_hits=cache_hits,
                            cache_misses=cache_misses,
                            total_retries=total_retries,
                        )
                    return AgentResult(
                        success=True,
                        content=final_content,
                        dashboard=None,
                        tool_calls_log=tool_calls_log,
                        total_steps=step + 1,
                        total_tokens=total_tokens,
                        provider=provider_used,
                        error=None,
                        total_tool_time=total_tool_time,
                        cache_hits=cache_hits,
                        cache_misses=cache_misses,
                        total_retries=total_retries,
                    )

        # Max steps exceeded
        logger.warning(f"Agent hit max steps ({self.max_steps})")
        cache_stats = self.tool_registry.get_cache_stats()
        return AgentResult(
            success=False,
            content="",
            tool_calls_log=tool_calls_log,
            total_steps=self.max_steps,
            total_tokens=total_tokens,
            provider=provider_used,
            error=f"Agent exceeded max steps ({self.max_steps})",
            total_tool_time=total_tool_time,
            cache_hits=cache_stats.get("cache_hits", 0),
            cache_misses=cache_stats.get("cache_misses", 0),
            total_retries=total_retries,
        )
