# -*- coding: utf-8 -*-
"""Backtest API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    code: Optional[str] = Field(None, description="仅回测指定股票")
    force: bool = Field(False, description="强制重新计算")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易日数）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="分析记录最小天龄（0=不限）")
    limit: int = Field(200, ge=1, le=2000, description="最多处理的分析记录数")


class ProfileBacktestRunRequest(BaseModel):
    profile_name: str = Field(..., description="画像名称", examples=["mag7", "nasdaq100"])
    strategy_name: str = Field(..., description="策略名称", examples=["mag7_breakout"])
    stock_codes: Optional[List[str]] = Field(None, description="可选：只回测指定股票列表")
    analysis_date_from: Optional[str] = Field(None, description="信号起始日期 YYYY-MM-DD")
    analysis_date_to: Optional[str] = Field(None, description="信号结束日期 YYYY-MM-DD")
    eval_window_days: int = Field(10, ge=1, le=60, description="持有窗口（交易日数）")
    only_passed: bool = Field(True, description="仅统计通过策略阈值的信号")


class BacktestRunResponse(BaseModel):
    processed: int = Field(..., description="候选记录数")
    saved: int = Field(..., description="写入回测结果数")
    completed: int = Field(..., description="完成回测数")
    insufficient: int = Field(..., description="数据不足数")
    errors: int = Field(..., description="错误数")


class ProfileBacktestSummary(BaseModel):
    total_signals: int
    wins: int
    losses: int
    neutrals: int
    win_rate_pct: Optional[float] = None
    avg_return_pct: Optional[float] = None
    avg_max_return_pct: Optional[float] = None
    avg_min_return_pct: Optional[float] = None
    eval_window_days: int
    by_code: Dict[str, Any] = Field(default_factory=dict)


class ProfileBacktestResultItem(BaseModel):
    code: str
    stock_name: str
    analysis_date: str
    entry_date: str
    exit_date: str
    score: int
    grade: str
    verdict: str
    entry_price: float
    exit_price: float
    max_return_pct: float
    min_return_pct: float
    window_return_pct: float
    outcome: str


class ProfileBacktestRunResponse(BaseModel):
    profile_name: str
    strategy_name: str
    display_name: str
    eval_window_days: int
    summary: ProfileBacktestSummary
    items: List[ProfileBacktestResultItem] = Field(default_factory=list)


class BacktestResultItem(BaseModel):
    analysis_history_id: int
    code: str
    stock_name: Optional[str] = None
    analysis_date: Optional[str] = None
    eval_window_days: int
    engine_version: str
    eval_status: str
    evaluated_at: Optional[str] = None
    operation_advice: Optional[str] = None
    trend_prediction: Optional[str] = None
    position_recommendation: Optional[str] = None
    start_price: Optional[float] = None
    end_close: Optional[float] = None
    max_high: Optional[float] = None
    min_low: Optional[float] = None
    stock_return_pct: Optional[float] = None
    actual_return_pct: Optional[float] = None
    actual_movement: Optional[str] = None
    direction_expected: Optional[str] = None
    direction_correct: Optional[bool] = None
    outcome: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    hit_stop_loss: Optional[bool] = None
    hit_take_profit: Optional[bool] = None
    first_hit: Optional[str] = None
    first_hit_date: Optional[str] = None
    first_hit_trading_days: Optional[int] = None
    simulated_entry_price: Optional[float] = None
    simulated_exit_price: Optional[float] = None
    simulated_exit_reason: Optional[str] = None
    simulated_return_pct: Optional[float] = None


class BacktestResultsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BacktestResultItem] = Field(default_factory=list)


class PerformanceMetrics(BaseModel):
    scope: str
    code: Optional[str] = None
    eval_window_days: int
    engine_version: str
    computed_at: Optional[str] = None

    total_evaluations: int
    completed_count: int
    insufficient_count: int
    long_count: int
    cash_count: int
    win_count: int
    loss_count: int
    neutral_count: int

    direction_accuracy_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    neutral_rate_pct: Optional[float] = None
    avg_stock_return_pct: Optional[float] = None
    avg_simulated_return_pct: Optional[float] = None

    stop_loss_trigger_rate: Optional[float] = None
    take_profit_trigger_rate: Optional[float] = None
    ambiguous_rate: Optional[float] = None
    avg_days_to_first_hit: Optional[float] = None

    advice_breakdown: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
