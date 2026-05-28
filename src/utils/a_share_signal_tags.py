# -*- coding: utf-8 -*-
"""
Helpers for deriving reusable A-share signal tags from analysis snapshots.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.utils.data_processing import extract_fundamental_context, parse_json_field


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def derive_a_share_signal_tags(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Optional[Dict[str, Any]]:
    """
    Derive reusable A-share signal tags from saved analysis context.

    Returns ``None`` for non-A-share or when no useful tag can be inferred.
    """
    snapshot = parse_json_field(context_snapshot)
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    enhanced = _as_dict(snapshot.get("enhanced_context"))
    trend = _as_dict(enhanced.get("trend_analysis"))
    realtime = _as_dict(enhanced.get("realtime"))
    fundamental = extract_fundamental_context(snapshot, fallback_fundamental_payload)
    fundamental = fundamental if isinstance(fundamental, dict) else {}

    market = str(fundamental.get("market") or "").strip().lower()
    if not market:
        code = str(enhanced.get("code") or snapshot.get("stock_code") or "").strip().upper()
        if code and code[:1].isalpha():
            market = "us"
        else:
            market = "cn"
    if market != "cn":
        return None

    tags: List[str] = []
    labels: List[str] = []

    intraday_pattern = str(trend.get("intraday_pattern") or "").strip()
    if intraday_pattern:
        tags.append(f"intraday:{intraday_pattern}")
        labels.append(f"日内结构:{intraday_pattern}")

    if trend.get("weak_close") is True:
        tags.append("risk:weak_close")
        labels.append("弱收")
    if trend.get("near_limit_up") is True:
        tags.append("emotion:near_limit_up")
        labels.append("接近涨停")
    if trend.get("near_limit_down") is True:
        tags.append("risk:near_limit_down")
        labels.append("接近跌停")

    upper_shadow = _safe_float(trend.get("upper_shadow_pct"))
    if upper_shadow is not None and upper_shadow >= 3:
        tags.append("risk:long_upper_shadow")
        labels.append("长上影")

    volume_status = str(trend.get("volume_status") or "").strip()
    if volume_status:
        tags.append(f"volume:{volume_status}")
        labels.append(f"量能:{volume_status}")
    if volume_status == "放量下跌":
        tags.append("risk:heavy_volume_down")
        labels.append("放量下跌")

    turnover_rate = _safe_float(realtime.get("turnover_rate"))
    if turnover_rate is not None:
        if turnover_rate >= 15:
            tags.append("turnover:very_high")
            labels.append("高换手")
        elif turnover_rate >= 8:
            tags.append("turnover:elevated")
            labels.append("换手偏高")

    capital_flow_data = _as_dict(_as_dict(fundamental.get("capital_flow")).get("data"))
    stock_flow = _as_dict(capital_flow_data.get("stock_flow"))
    main_net_inflow = _safe_float(stock_flow.get("main_net_inflow"))
    inflow_5d = _safe_float(stock_flow.get("inflow_5d"))
    if main_net_inflow is not None:
        if main_net_inflow > 0:
            tags.append("flow:main_inflow")
            labels.append("主力净流入")
        elif main_net_inflow < 0:
            tags.append("flow:main_outflow")
            labels.append("主力净流出")
    if inflow_5d is not None:
        if inflow_5d > 0:
            tags.append("flow:5d_positive")
            labels.append("5日资金偏正")
        elif inflow_5d < 0:
            tags.append("flow:5d_negative")
            labels.append("5日资金偏负")

    dragon_tiger_data = _as_dict(_as_dict(fundamental.get("dragon_tiger")).get("data"))
    if dragon_tiger_data.get("is_on_list") is True:
        tags.append("attention:dragon_tiger")
        labels.append("龙虎榜异动")

    boards = _as_list(fundamental.get("belong_boards"))
    if boards:
        tags.append("board:has_membership")
        labels.append("有板块归属")

    board_data = _as_dict(_as_dict(fundamental.get("boards")).get("data"))
    if _as_list(board_data.get("top")):
        tags.append("board:top_performer_exists")
        labels.append("板块强势榜可用")
    if _as_list(board_data.get("bottom")):
        tags.append("board:bottom_performer_exists")
        labels.append("板块弱势榜可用")

    if not tags:
        return None

    return {
        "market": "cn",
        "tags": tags,
        "labels": labels,
        "intraday_pattern": intraday_pattern or None,
        "volume_status": volume_status or None,
        "turnover_rate": turnover_rate,
        "main_net_inflow": main_net_inflow,
        "inflow_5d": inflow_5d,
        "near_limit_up": bool(trend.get("near_limit_up")),
        "near_limit_down": bool(trend.get("near_limit_down")),
        "weak_close": bool(trend.get("weak_close")),
        "dragon_tiger": bool(dragon_tiger_data.get("is_on_list")),
    }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
