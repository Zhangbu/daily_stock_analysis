# -*- coding: utf-8 -*-
"""LLM response parsing helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Type

from json_repair import repair_json

logger = logging.getLogger(__name__)


def fix_json_string(json_str: str) -> str:
    """Repair common JSON formatting issues produced by LLMs."""
    json_str = re.sub(r"//.*?\n", "\n", json_str)
    json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)
    json_str = json_str.replace("True", "true").replace("False", "false")
    return repair_json(json_str)


def parse_text_response(response_text: str, code: str, name: str, result_cls: Type) -> Any:
    """Build a fallback analysis result from plain text content."""
    sentiment_score = 50
    trend = "震荡"
    advice = "持有"
    text_lower = response_text.lower()

    positive_keywords = ["看多", "买入", "上涨", "突破", "强势", "利好", "加仓", "bullish", "buy"]
    negative_keywords = ["看空", "卖出", "下跌", "跌破", "弱势", "利空", "减仓", "bearish", "sell"]
    positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
    negative_count = sum(1 for kw in negative_keywords if kw in text_lower)

    if positive_count > negative_count + 1:
        sentiment_score = 65
        trend = "看多"
        advice = "买入"
        decision_type = "buy"
    elif negative_count > positive_count + 1:
        sentiment_score = 35
        trend = "看空"
        advice = "卖出"
        decision_type = "sell"
    else:
        decision_type = "hold"

    summary = response_text[:500] if response_text else "无分析结果"
    return result_cls(
        code=code,
        name=name,
        sentiment_score=sentiment_score,
        trend_prediction=trend,
        operation_advice=advice,
        decision_type=decision_type,
        confidence_level="低",
        analysis_summary=summary,
        key_points="JSON解析失败，仅供参考",
        risk_warning="分析结果可能不准确，建议结合其他信息判断",
        raw_response=response_text,
        success=True,
    )


def parse_response(response_text: str, code: str, name: str, result_cls: Type) -> Any:
    """Parse a structured LLM response into an AnalysisResult-compatible object."""
    try:
        cleaned_text = response_text
        if "```json" in cleaned_text:
            cleaned_text = cleaned_text.replace("```json", "").replace("```", "")
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.replace("```", "")

        json_start = cleaned_text.find("{")
        json_end = cleaned_text.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            logger.warning("无法从响应中提取 JSON，使用原始文本分析")
            return parse_text_response(response_text, code, name, result_cls)

        data = json.loads(fix_json_string(cleaned_text[json_start:json_end]))
        dashboard = data.get("dashboard")

        ai_stock_name = data.get("stock_name")
        if ai_stock_name and (name.startswith("股票") or name == code or "Unknown" in name):
            name = ai_stock_name

        decision_type = data.get("decision_type", "")
        if not decision_type:
            operation_advice = data.get("operation_advice", "持有")
            if operation_advice in ["买入", "加仓", "强烈买入"]:
                decision_type = "buy"
            elif operation_advice in ["卖出", "减仓", "强烈卖出"]:
                decision_type = "sell"
            else:
                decision_type = "hold"

        # Ensure dashboard is a dict, not a string (LLM JSON parsing issue fix)
        if isinstance(dashboard, str):
            try:
                dashboard = json.loads(fix_json_string(dashboard))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"dashboard JSON 解析失败：{e}")
                dashboard = {}

        return result_cls(
            code=code,
            name=name,
            sentiment_score=int(data.get("sentiment_score", 50)),
            trend_prediction=data.get("trend_prediction", "震荡"),
            operation_advice=data.get("operation_advice", "持有"),
            decision_type=decision_type,
            confidence_level=data.get("confidence_level", "中"),
            dashboard=dashboard,
            trend_analysis=data.get("trend_analysis", ""),
            short_term_outlook=data.get("short_term_outlook", ""),
            medium_term_outlook=data.get("medium_term_outlook", ""),
            technical_analysis=data.get("technical_analysis", ""),
            ma_analysis=data.get("ma_analysis", ""),
            volume_analysis=data.get("volume_analysis", ""),
            pattern_analysis=data.get("pattern_analysis", ""),
            fundamental_analysis=data.get("fundamental_analysis", ""),
            sector_position=data.get("sector_position", ""),
            company_highlights=data.get("company_highlights", ""),
            news_summary=data.get("news_summary", ""),
            market_sentiment=data.get("market_sentiment", ""),
            hot_topics=data.get("hot_topics", ""),
            analysis_summary=data.get("analysis_summary", "分析完成"),
            key_points=data.get("key_points", ""),
            risk_warning=data.get("risk_warning", ""),
            buy_reason=data.get("buy_reason", ""),
            search_performed=data.get("search_performed", False),
            data_sources=data.get("data_sources", "技术面数据"),
            success=True,
        )
    except json.JSONDecodeError as exc:
        logger.warning(f"JSON 解析失败: {exc}，尝试从文本提取")
        return parse_text_response(response_text, code, name, result_cls)
