# -*- coding: utf-8 -*-
"""Quality guards and stage-latency helpers for stock analysis pipeline."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any, Dict, Optional

from utils.observability import metrics_store


class StageLatencyRecorder:
    """Record and log stage-level latency for pipeline diagnosis."""

    def __init__(self, *, logger: logging.Logger) -> None:
        self.logger = logger

    def log(self, *, code: str, stage_name: str, started_at: float) -> None:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        metrics_store.record(
            operation=f"pipeline_stage_{stage_name}",
            status="ok",
            duration_ms=elapsed_ms,
            cache_hit=None,
            provider=None,
        )
        self.logger.info(f"[{code}] stage={stage_name} duration_ms={elapsed_ms}")


class AnalysisQualityGuard:
    """Apply stale-data and completeness guards to reduce overconfident outputs."""

    def __init__(self, *, config: Any, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger

    def get_data_age_days(self, *, code: str, persistence: Any) -> Optional[int]:
        """Return age in days for latest available context date."""
        try:
            context = persistence.get_analysis_context(code)
        except Exception:
            return None
        if not context:
            return None

        context_date = context.get("date")
        if not context_date:
            return None

        return self.compute_data_age_days_from_context_date(context_date, code=code)

    def compute_data_age_days_from_context_date(
        self,
        context_date: Any,
        *,
        code: str = "",
    ) -> Optional[int]:
        """Compute age-in-days from a context date value."""
        if context_date in (None, ""):
            return None
        try:
            if isinstance(context_date, date):
                latest_date = context_date
            else:
                date_text = str(context_date).strip()
                latest_date = datetime.fromisoformat(date_text).date()
        except Exception:
            if code:
                self.logger.debug(f"[{code}] 无法解析分析上下文日期: {context_date}")
            return None
        return max((date.today() - latest_date).days, 0)

    def apply_stale_data_guard(
        self,
        *,
        result: Any,
        code: str,
        data_age_days: Optional[int],
        fetch_success: bool,
    ) -> None:
        """Downgrade advice when market data is stale to reduce false confidence."""
        if data_age_days is None:
            return

        stale_limit = max(0, int(getattr(self.config, "analysis_stale_days_limit", 2)))
        should_downgrade = data_age_days > stale_limit or (not fetch_success and data_age_days > 0)
        if not should_downgrade:
            return

        stale_note = (
            f"行情数据非最新（最新数据距今 {data_age_days} 天，阈值 {stale_limit} 天）, 已自动降级为观望。"
        )
        result.operation_advice = "观望"
        result.decision_type = "hold"
        result.confidence_level = "低"
        result.sentiment_score = min(max(result.sentiment_score, 40), 60)
        result.analysis_summary = (f"{result.analysis_summary} {stale_note}").strip()
        result.risk_warning = (f"{result.risk_warning} {stale_note}").strip()
        self.logger.warning(f"[{code}] {stale_note}")

    def apply_data_completeness_guard(
        self,
        *,
        result: Any,
        code: str,
        context: Dict[str, Any],
        trend_result: Optional[Any],
        news_context: str,
        realtime_quote: Any,
    ) -> None:
        """Downgrade confidence when key analysis dimensions are missing."""
        missing_historical = bool(context.get("data_missing"))
        has_realtime = bool(realtime_quote and getattr(realtime_quote, "price", None))
        has_trend = trend_result is not None
        has_news = bool((news_context or "").strip())

        if missing_historical and not has_realtime:
            note = "历史与实时行情均缺失，分析已自动降级为观望。"
            result.operation_advice = "观望"
            result.decision_type = "hold"
            result.confidence_level = "低"
            result.sentiment_score = min(max(result.sentiment_score, 40), 60)
            result.analysis_summary = f"{result.analysis_summary} {note}".strip()
            result.risk_warning = f"{result.risk_warning} {note}".strip()
            self.logger.warning(f"[{code}] {note}")
            return

        missing_dimensions = 0
        if not has_trend:
            missing_dimensions += 1
        if not has_news:
            missing_dimensions += 1
        if missing_dimensions == 0:
            return

        if missing_dimensions >= 2:
            result.confidence_level = "低"
        elif result.confidence_level == "高":
            result.confidence_level = "中"

        note = "部分关键分析维度缺失（趋势/情报），请结合盘中数据谨慎决策。"
        result.risk_warning = f"{result.risk_warning} {note}".strip()
        self.logger.info(f"[{code}] Data completeness guard applied, missing_dimensions={missing_dimensions}")
