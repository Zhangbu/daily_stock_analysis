# -*- coding: utf-8 -*-
"""
Executable signal engine for profile-based strategy runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pandas as pd

from src.stock_analyzer import BuySignal, TrendAnalysisResult, TrendStatus, VolumeStatus


@dataclass
class StrategySignal:
    strategy_name: str
    score: int
    grade: str
    passed: bool
    verdict: str
    entry_zone: str
    stop_loss: str
    target_hint: str
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class StrategySignalEngine:
    """Evaluate executable rules for profile-driven strategies."""

    def evaluate(
        self,
        strategy_name: str,
        df: pd.DataFrame,
        trend_result: TrendAnalysisResult,
        parameters: Dict[str, Any],
    ) -> StrategySignal:
        if strategy_name == "mag7_ma_pullback":
            return self._evaluate_mag7_ma_pullback(df, trend_result, parameters)
        if strategy_name == "mag7_breakout":
            return self._evaluate_mag7_breakout(df, trend_result, parameters)
        if strategy_name == "mag7_ma_cross":
            return self._evaluate_mag7_ma_cross(df, trend_result, parameters)
        raise ValueError(f"Unsupported executable strategy: {strategy_name}")

    def _evaluate_mag7_ma_pullback(
        self,
        df: pd.DataFrame,
        trend_result: TrendAnalysisResult,
        parameters: Dict[str, Any],
    ) -> StrategySignal:
        latest = df.sort_values("date").reset_index(drop=True).iloc[-1]
        price = float(latest["close"])
        ma5 = float(trend_result.ma5)
        ma10 = float(trend_result.ma10)
        ma20 = float(trend_result.ma20)
        ma60 = float(trend_result.ma60)

        distance_ma5 = abs(price - ma5) / ma5 * 100 if ma5 else 999.0
        distance_ma10 = abs(price - ma10) / ma10 * 100 if ma10 else 999.0
        volume_ratio_5d = float(trend_result.volume_ratio_5d or 0.0)

        pullback_to_ma5_pct = float(parameters.get("pullback_to_ma5_pct", 1.0))
        pullback_to_ma10_pct = float(parameters.get("pullback_to_ma10_pct", 1.5))
        max_bias_ma5_pct = float(parameters.get("max_bias_ma5_pct", 3.5))
        volume_ratio_max = float(parameters.get("volume_ratio_max", 0.9))
        breakout_lookback_days = max(3, int(parameters.get("breakout_lookback_days", 5)))
        stop_loss_below_ma20_pct = float(parameters.get("stop_loss_below_ma20_pct", 1.5))
        target_reward_risk = float(parameters.get("target_reward_risk", 2.0))
        require_ma20_above_ma60 = bool(parameters.get("ma20_above_ma60_required", True))
        require_close_above_ma20 = bool(parameters.get("close_above_ma20_required", True))

        reasons: List[str] = []
        risks: List[str] = []
        score = 0

        is_bull_alignment = ma5 >= ma10 >= ma20
        if is_bull_alignment:
            score += 25
            reasons.append("MA5/MA10/MA20 保持多头顺序。")
        else:
            risks.append("短中期均线未形成理想多头顺序。")

        if require_ma20_above_ma60 and ma20 >= ma60:
            score += 15
            reasons.append("MA20 位于 MA60 上方，中期趋势保持向上。")
        elif require_ma20_above_ma60:
            risks.append("MA20 未站上 MA60，中期趋势确认不足。")

        if require_close_above_ma20 and price >= ma20:
            score += 10
            reasons.append("收盘价仍守在 MA20 上方。")
        elif require_close_above_ma20:
            risks.append("收盘价跌回 MA20 下方，结构转弱。")

        if distance_ma5 <= pullback_to_ma5_pct:
            score += 18
            reasons.append(f"价格贴近 MA5（偏离 {distance_ma5:.2f}%），属于强势回踩。")
        elif distance_ma10 <= pullback_to_ma10_pct:
            score += 15
            reasons.append(f"价格贴近 MA10（偏离 {distance_ma10:.2f}%），属于中继回踩。")
        else:
            risks.append("当前价格距离 MA5/MA10 较远，回踩博弈位置一般。")

        if trend_result.bias_ma5 <= max_bias_ma5_pct:
            score += 10
            reasons.append(f"距 MA5 的乖离率为 {trend_result.bias_ma5:.2f}%，仍在可接受区间。")
        else:
            risks.append(f"距 MA5 的乖离率为 {trend_result.bias_ma5:.2f}%，存在追高风险。")

        if volume_ratio_5d > 0 and volume_ratio_5d <= volume_ratio_max:
            score += 12
            reasons.append(f"量能为 5 日均量的 {volume_ratio_5d:.2f} 倍，呈现缩量回踩特征。")
        elif trend_result.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("回踩伴随放量下跌，承接强度不足。")
        else:
            risks.append("量能未明显缩至理想区间，洗盘确认度一般。")

        recent_high_window = df["high"].iloc[-(breakout_lookback_days + 1):-1]
        recent_high = float(recent_high_window.max()) if not recent_high_window.empty else price
        if recent_high and price >= recent_high * 0.97:
            score += 5
            reasons.append("回踩前价格仍贴近近期高位，趋势延续性较好。")

        if trend_result.buy_signal in {BuySignal.STRONG_BUY, BuySignal.BUY}:
            score += 5
            reasons.append(f"技术分析器当前给出 {trend_result.buy_signal.value} 信号。")
        elif trend_result.buy_signal in {BuySignal.SELL, BuySignal.STRONG_SELL}:
            risks.append(f"技术分析器当前给出 {trend_result.buy_signal.value} 信号。")

        if trend_result.trend_status in {TrendStatus.STRONG_BULL, TrendStatus.BULL}:
            score += 5
        elif trend_result.trend_status in {TrendStatus.BEAR, TrendStatus.STRONG_BEAR}:
            score -= 10

        stop_loss_value = ma20 * (1 - stop_loss_below_ma20_pct / 100) if ma20 else price * 0.97
        risk_per_share = max(price - stop_loss_value, price * 0.01)
        target_price = price + risk_per_share * target_reward_risk

        if score >= 80:
            grade = "A"
            verdict = "可重点观察"
            passed = True
        elif score >= 65:
            grade = "B"
            verdict = "有条件关注"
            passed = True
        elif score >= 50:
            grade = "C"
            verdict = "继续跟踪"
            passed = False
        else:
            grade = "D"
            verdict = "暂时回避"
            passed = False

        if require_close_above_ma20 and price < ma20:
            grade = "D"
            verdict = "跌破防守位，暂不参与"
            passed = False

        entry_zone = f"MA5 {ma5:.2f} - MA10 {ma10:.2f}"
        stop_loss = f"{stop_loss_value:.2f} (参考 MA20 下方 {stop_loss_below_ma20_pct:.1f}%)"
        target_hint = f"{target_price:.2f} (按 {target_reward_risk:.1f}:1 风险收益估算)"

        return StrategySignal(
            strategy_name="mag7_ma_pullback",
            score=max(0, min(100, int(round(score)))),
            grade=grade,
            passed=passed,
            verdict=verdict,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            target_hint=target_hint,
            reasons=reasons,
            risks=risks,
            metrics={
                "price": round(price, 2),
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "distance_to_ma5_pct": round(distance_ma5, 2),
                "distance_to_ma10_pct": round(distance_ma10, 2),
                "volume_ratio_5d": round(volume_ratio_5d, 2),
            },
        )

    def _evaluate_mag7_breakout(
        self,
        df: pd.DataFrame,
        trend_result: TrendAnalysisResult,
        parameters: Dict[str, Any],
    ) -> StrategySignal:
        ordered_df = df.sort_values("date").reset_index(drop=True)
        latest = ordered_df.iloc[-1]
        price = float(latest["close"])
        ma5 = float(trend_result.ma5)
        ma10 = float(trend_result.ma10)
        ma20 = float(trend_result.ma20)
        ma60 = float(trend_result.ma60)

        breakout_lookback_days = max(10, int(parameters.get("breakout_lookback_days", 20)))
        breakout_buffer_pct = float(parameters.get("breakout_buffer_pct", 0.5))
        max_breakout_extension_pct = float(parameters.get("max_breakout_extension_pct", 4.0))
        volume_ratio_min = float(parameters.get("volume_ratio_min", 1.2))
        stop_loss_below_breakout_pct = float(parameters.get("stop_loss_below_breakout_pct", 2.0))
        target_reward_risk = float(parameters.get("target_reward_risk", 2.5))
        require_ma20_above_ma60 = bool(parameters.get("ma20_above_ma60_required", True))
        require_close_above_ma20 = bool(parameters.get("close_above_ma20_required", True))

        recent_high_window = ordered_df["high"].iloc[-(breakout_lookback_days + 1):-1]
        breakout_level = float(recent_high_window.max()) if not recent_high_window.empty else price
        breakout_pct = ((price - breakout_level) / breakout_level * 100) if breakout_level else 0.0
        volume_ratio_5d = float(trend_result.volume_ratio_5d or 0.0)

        reasons: List[str] = []
        risks: List[str] = []
        score = 0

        is_bull_alignment = ma5 >= ma10 >= ma20
        if is_bull_alignment:
            score += 20
            reasons.append("MA5/MA10/MA20 维持多头顺序，具备突破延续基础。")
        else:
            risks.append("短中期均线顺序一般，突破后的持续性可能偏弱。")

        if require_ma20_above_ma60 and ma20 >= ma60:
            score += 15
            reasons.append("MA20 位于 MA60 上方，中期趋势支持继续上攻。")
        elif require_ma20_above_ma60:
            risks.append("MA20 未明显强于 MA60，中期趋势背景一般。")

        if require_close_above_ma20 and price >= ma20:
            score += 10
            reasons.append("收盘价保持在 MA20 上方。")
        elif require_close_above_ma20:
            risks.append("收盘价未站稳 MA20，上攻结构不完整。")

        if breakout_pct >= breakout_buffer_pct:
            score += 25
            reasons.append(
                f"收盘价高于最近 {breakout_lookback_days} 日高点 {breakout_level:.2f}，突破幅度 {breakout_pct:.2f}%。"
            )
        elif breakout_pct >= 0:
            score += 12
            reasons.append(
                f"价格已经贴近最近 {breakout_lookback_days} 日高点 {breakout_level:.2f}，但突破确认仍偏弱。"
            )
        else:
            risks.append(f"当前价格仍低于最近 {breakout_lookback_days} 日高点，尚未形成有效突破。")

        if breakout_pct <= max_breakout_extension_pct:
            score += 10
            reasons.append(f"突破后仅延伸 {breakout_pct:.2f}%，尚未进入明显追高区。")
        else:
            risks.append(f"突破后已延伸 {breakout_pct:.2f}%，短线追高风险增大。")

        if volume_ratio_5d >= volume_ratio_min:
            score += 15
            reasons.append(f"量能达到 5 日均量的 {volume_ratio_5d:.2f} 倍，突破获得量能确认。")
        elif trend_result.volume_status == VolumeStatus.HEAVY_VOLUME_UP:
            score += 10
            reasons.append("量价齐升，突破动能较强。")
        else:
            risks.append("量能没有明显放大，需防假突破。")

        if trend_result.buy_signal in {BuySignal.STRONG_BUY, BuySignal.BUY}:
            score += 5
            reasons.append(f"技术分析器当前给出 {trend_result.buy_signal.value} 信号。")
        elif trend_result.buy_signal in {BuySignal.SELL, BuySignal.STRONG_SELL}:
            risks.append(f"技术分析器当前给出 {trend_result.buy_signal.value} 信号。")

        if trend_result.macd_bar > 0:
            score += 5
            reasons.append("MACD 柱体位于零轴上方，趋势惯性偏强。")

        breakout_stop = breakout_level * (1 - stop_loss_below_breakout_pct / 100) if breakout_level else price * 0.97
        risk_per_share = max(price - breakout_stop, price * 0.01)
        target_price = price + risk_per_share * target_reward_risk

        if score >= 82:
            grade = "A"
            verdict = "突破确认较强"
            passed = True
        elif score >= 68:
            grade = "B"
            verdict = "接近可执行突破"
            passed = True
        elif score >= 52:
            grade = "C"
            verdict = "继续观察确认"
            passed = False
        else:
            grade = "D"
            verdict = "暂不追突破"
            passed = False

        if require_close_above_ma20 and price < ma20:
            grade = "D"
            verdict = "失守趋势均线，放弃突破假设"
            passed = False

        entry_zone = f"Breakout {breakout_level:.2f} 附近，回踩不破可继续跟踪"
        stop_loss = f"{breakout_stop:.2f} (参考突破位下方 {stop_loss_below_breakout_pct:.1f}%)"
        target_hint = f"{target_price:.2f} (按 {target_reward_risk:.1f}:1 风险收益估算)"

        return StrategySignal(
            strategy_name="mag7_breakout",
            score=max(0, min(100, int(round(score)))),
            grade=grade,
            passed=passed,
            verdict=verdict,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            target_hint=target_hint,
            reasons=reasons,
            risks=risks,
            metrics={
                "price": round(price, 2),
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "breakout_level": round(breakout_level, 2),
                "breakout_pct": round(breakout_pct, 2),
                "volume_ratio_5d": round(volume_ratio_5d, 2),
            },
        )

    def _evaluate_mag7_ma_cross(
        self,
        df: pd.DataFrame,
        trend_result: TrendAnalysisResult,
        parameters: Dict[str, Any],
    ) -> StrategySignal:
        ordered_df = df.sort_values("date").reset_index(drop=True).copy()
        latest = ordered_df.iloc[-1]
        price = float(latest["close"])
        ma5 = float(trend_result.ma5)
        ma10 = float(trend_result.ma10)
        ma20 = float(trend_result.ma20)
        ma60 = float(trend_result.ma60)
        volume_ratio_5d = float(trend_result.volume_ratio_5d or 0.0)

        cross_lookback_days = max(1, int(parameters.get("cross_lookback_days", 3)))
        max_bias_ma5_pct = float(parameters.get("max_bias_ma5_pct", 4.0))
        volume_ratio_min = float(parameters.get("volume_ratio_min", 0.9))
        stop_loss_below_ma10_pct = float(parameters.get("stop_loss_below_ma10_pct", 1.5))
        target_reward_risk = float(parameters.get("target_reward_risk", 2.0))
        require_ma20_above_ma60 = bool(parameters.get("ma20_above_ma60_required", True))
        require_close_above_ma20 = bool(parameters.get("close_above_ma20_required", True))

        reasons: List[str] = []
        risks: List[str] = []
        score = 0

        short_diff = ordered_df["ma5"] - ordered_df["ma10"]
        mid_diff = ordered_df["ma10"] - ordered_df["ma20"]

        short_cross_days_ago = None
        for offset in range(1, min(cross_lookback_days + 1, len(ordered_df))):
            current_idx = len(ordered_df) - offset
            prev_idx = current_idx - 1
            if prev_idx < 0:
                break
            if short_diff.iloc[prev_idx] <= 0 < short_diff.iloc[current_idx]:
                short_cross_days_ago = offset - 1
                break

        mid_cross_days_ago = None
        for offset in range(1, min(cross_lookback_days + 1, len(ordered_df))):
            current_idx = len(ordered_df) - offset
            prev_idx = current_idx - 1
            if prev_idx < 0:
                break
            if mid_diff.iloc[prev_idx] <= 0 < mid_diff.iloc[current_idx]:
                mid_cross_days_ago = offset - 1
                break

        if short_cross_days_ago is not None:
            freshness_score = max(12, 20 - short_cross_days_ago * 4)
            score += freshness_score
            reasons.append(f"最近 {short_cross_days_ago + 1} 个交易日内出现 MA5 上穿 MA10。")
        elif ma5 >= ma10:
            score += 10
            reasons.append("MA5 仍位于 MA10 上方，但最新金叉已不算新鲜。")
        else:
            risks.append("MA5 尚未站上 MA10，短线拐点尚未确认。")

        if mid_cross_days_ago is not None:
            score += 10
            reasons.append(f"最近 {mid_cross_days_ago + 1} 个交易日内出现 MA10 上穿 MA20。")
        elif ma10 >= ma20:
            score += 8
            reasons.append("MA10 已位于 MA20 上方，中期趋势背景较稳。")
        else:
            risks.append("MA10 仍弱于 MA20，中期趋势支撑一般。")

        if require_ma20_above_ma60 and ma20 >= ma60:
            score += 15
            reasons.append("MA20 位于 MA60 上方，趋势地基完整。")
        elif require_ma20_above_ma60:
            risks.append("MA20 未站上 MA60，长一层趋势确认不足。")

        if require_close_above_ma20 and price >= ma20:
            score += 10
            reasons.append("收盘价位于 MA20 上方，价格没有脱离主趋势。")
        elif require_close_above_ma20:
            risks.append("收盘价跌回 MA20 下方，金叉质量明显下降。")

        if trend_result.bias_ma5 <= max_bias_ma5_pct:
            score += 12
            reasons.append(f"当前距 MA5 的乖离率为 {trend_result.bias_ma5:.2f}%，未明显追高。")
        else:
            risks.append(f"当前距 MA5 的乖离率为 {trend_result.bias_ma5:.2f}%，金叉后追高风险偏大。")

        if volume_ratio_5d >= volume_ratio_min:
            score += 10
            reasons.append(f"量能达到 5 日均量的 {volume_ratio_5d:.2f} 倍，金叉具备一定成交支持。")
        elif trend_result.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            score += 4
            reasons.append("量能偏平，但没有出现明显放量杀跌。")
        else:
            risks.append("量能未给出明确确认，需防震荡假金叉。")

        if trend_result.macd_bar > 0:
            score += 6
            reasons.append("MACD 柱体位于零轴上方，拐点后的惯性偏正。")
        if trend_result.buy_signal in {BuySignal.STRONG_BUY, BuySignal.BUY}:
            score += 5
            reasons.append(f"技术分析器当前给出 {trend_result.buy_signal.value} 信号。")
        elif trend_result.buy_signal in {BuySignal.SELL, BuySignal.STRONG_SELL}:
            risks.append(f"技术分析器当前给出 {trend_result.buy_signal.value} 信号。")

        stop_loss_value = ma10 * (1 - stop_loss_below_ma10_pct / 100) if ma10 else price * 0.97
        risk_per_share = max(price - stop_loss_value, price * 0.01)
        target_price = price + risk_per_share * target_reward_risk

        if score >= 82:
            grade = "A"
            verdict = "金叉确认较强"
            passed = True
        elif score >= 68:
            grade = "B"
            verdict = "可跟踪均线拐点"
            passed = True
        elif score >= 52:
            grade = "C"
            verdict = "继续观察均线确认"
            passed = False
        else:
            grade = "D"
            verdict = "暂不采用金叉策略"
            passed = False

        if require_close_above_ma20 and price < ma20:
            grade = "D"
            verdict = "价格失守 MA20，放弃金叉假设"
            passed = False

        entry_zone = f"MA5 {ma5:.2f} / MA10 {ma10:.2f} 附近"
        stop_loss = f"{stop_loss_value:.2f} (参考 MA10 下方 {stop_loss_below_ma10_pct:.1f}%)"
        target_hint = f"{target_price:.2f} (按 {target_reward_risk:.1f}:1 风险收益估算)"

        return StrategySignal(
            strategy_name="mag7_ma_cross",
            score=max(0, min(100, int(round(score)))),
            grade=grade,
            passed=passed,
            verdict=verdict,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            target_hint=target_hint,
            reasons=reasons,
            risks=risks,
            metrics={
                "price": round(price, 2),
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "volume_ratio_5d": round(volume_ratio_5d, 2),
                "short_cross_days_ago": float(short_cross_days_ago if short_cross_days_ago is not None else -1),
                "mid_cross_days_ago": float(mid_cross_days_ago if mid_cross_days_ago is not None else -1),
            },
        )
