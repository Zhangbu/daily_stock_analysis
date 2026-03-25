# -*- coding: utf-8 -*-
"""Signal strategy backtest API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class StrategySignalInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    supported: bool
    support_note: str


class StrategySignalListResponse(BaseModel):
    strategies: List[StrategySignalInfo] = Field(default_factory=list)


class StrategySignalBacktestRunRequest(BaseModel):
    code: str = Field(..., description="Stock code to backtest")
    strategy_ids: List[str] = Field(default_factory=list, description="Signal strategies to run")
    days: int = Field(240, ge=60, le=1000, description="Lookback trading days")
    initial_capital: float = Field(100000.0, gt=0, description="Initial portfolio capital")


class StrategySignalTradeItem(BaseModel):
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: float
    profit: float
    profit_pct: float


class StrategySignalMetrics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_profit: float
    avg_win: float
    avg_loss: float
    avg_profit_pct: float
    total_profit: float
    total_profit_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float


class StrategySignalBacktestItem(BaseModel):
    strategy_id: str
    strategy_name: str
    supported: bool
    note: Optional[str] = None
    metrics: StrategySignalMetrics
    trades: List[StrategySignalTradeItem] = Field(default_factory=list)


class StrategySignalBacktestRunResponse(BaseModel):
    code: str
    data_source: str
    days: int
    initial_capital: float
    results: List[StrategySignalBacktestItem] = Field(default_factory=list)
    unsupported_strategy_ids: List[str] = Field(default_factory=list)
