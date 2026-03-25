# -*- coding: utf-8 -*-
"""Persistence helpers extracted from the stock analysis pipeline."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, Iterable, Optional

from src.repositories.analysis_repo import AnalysisRepository
from src.repositories.news_repo import NewsIntelRepository
from src.repositories.stock_repo import StockRepository


class AnalysisPersistenceService:
    """Coordinate persistence operations used by the analysis pipeline."""

    def __init__(
        self,
        *,
        db,
        save_context_snapshot: bool,
        safe_to_dict: Callable[[Any], Optional[Dict[str, Any]]],
    ) -> None:
        self.db = db
        self.save_context_snapshot = save_context_snapshot
        self.safe_to_dict = safe_to_dict
        self.stock_repo = StockRepository(db)
        self.analysis_repo = AnalysisRepository(db)
        self.news_repo = NewsIntelRepository(db)

    def has_today_data(self, code: str, today: Optional[date] = None) -> bool:
        """Check whether the latest daily data is already available."""
        return self.stock_repo.has_today_data(code, today or date.today())

    def save_daily_data(self, df, code: str, source_name: str) -> int:
        """Persist fetched daily data."""
        return self.stock_repo.save_dataframe(df, code, source_name)

    def count_codes_with_today_data(self, codes: Iterable[str], today: Optional[date] = None) -> int:
        """Count how many stock codes already have daily data for the target date."""
        target_date = today or date.today()
        return sum(1 for code in codes if self.stock_repo.has_today_data(code, target_date))

    def get_data_range(self, code: str, start_date, end_date):
        """Load historical data range for indicator analysis."""
        return self.stock_repo.get_range(code, start_date, end_date)

    def get_analysis_context(self, code: str):
        """Load analysis context for a stock."""
        return self.stock_repo.get_analysis_context(code)

    def save_news_intel(
        self,
        *,
        code: str,
        name: str,
        dimension: str,
        query: str,
        response,
        query_context: Dict[str, str],
    ) -> None:
        """Persist fetched news or intel results."""
        self.news_repo.save(
            code=code,
            name=name,
            dimension=dimension,
            query=query,
            response=response,
            query_context=query_context,
        )

    def build_context_snapshot(
        self,
        *,
        enhanced_context: Dict[str, Any],
        news_content: Optional[str],
        realtime_quote: Any,
        chip_data: Any,
    ) -> Dict[str, Any]:
        """Build a serializable context snapshot for history records."""
        return {
            "enhanced_context": enhanced_context,
            "news_content": news_content,
            "realtime_quote_raw": self.safe_to_dict(realtime_quote),
            "chip_distribution_raw": self.safe_to_dict(chip_data),
        }

    def save_analysis_history(
        self,
        *,
        result,
        query_id: str,
        report_type: str,
        news_content: Optional[str],
        context_snapshot: Dict[str, Any],
    ) -> None:
        """Persist the analysis history record."""
        self.analysis_repo.save(
            result=result,
            query_id=query_id,
            report_type=report_type,
            news_content=news_content,
            context_snapshot=context_snapshot,
            save_snapshot=self.save_context_snapshot,
        )
