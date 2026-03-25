# -*- coding: utf-8 -*-
"""Notification rendering helpers."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from src.analyzer import AnalysisResult


def render_daily_report(service, results: List[AnalysisResult], report_date: Optional[str] = None) -> str:
    """Render the daily markdown report."""
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")
    return service._generate_daily_report_impl(results, report_date=report_date)


def render_dashboard_report(service, results: List[AnalysisResult], report_date: Optional[str] = None) -> str:
    """Render the dashboard markdown report."""
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")
    return service._generate_dashboard_report_impl(results, report_date=report_date)
