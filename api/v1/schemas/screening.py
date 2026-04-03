# -*- coding: utf-8 -*-
"""
===================================
Stock Screening Schemas
===================================
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class StockScreeningRequest(BaseModel):
    """Stock screening request parameters."""

    market: str = Field(
        default="cn",
        description="Market region: cn/us",
        pattern="^(cn|us)$",
    )
    data_mode: str = Field(
        default="database",
        description="Data mode: database/realtime",
        pattern="^(database|realtime)$",
    )
    
    min_market_cap: Optional[float] = Field(
        default=5_000_000_000,
        description="Minimum market cap in yuan (建议: 20亿-100亿)",
        ge=0
    )
    max_market_cap: Optional[float] = Field(
        default=None,
        description="Maximum market cap in yuan (optional)",
        ge=0
    )
    min_turnover: Optional[float] = Field(
        default=100_000_000,
        description="Minimum turnover in yuan (建议: 5千万-2亿)",
        ge=0
    )
    min_turnover_rate: Optional[float] = Field(
        default=1.0,
        description="Minimum turnover rate percentage",
        ge=0
    )
    max_turnover_rate: Optional[float] = Field(
        default=25.0,
        description="Maximum turnover rate percentage",
        ge=0
    )
    min_price: Optional[float] = Field(
        default=5.0,
        description="Minimum stock price in yuan (建议: 3元-50元)",
        ge=0
    )
    max_price: Optional[float] = Field(
        default=None,
        description="Maximum stock price in yuan (optional)",
        ge=0
    )
    min_change_pct: Optional[float] = Field(
        default=-3.0,
        description="Minimum change percentage",
        ge=-100,
        le=100
    )
    max_change_pct: Optional[float] = Field(
        default=10.0,
        description="Maximum change percentage",
        ge=-100,
        le=100
    )
    exclude_st: Optional[bool] = Field(
        default=True,
        description="Exclude ST stocks"
    )
    exclude_prefixes: Optional[List[str]] = Field(
        default=[],
        description="Exclude stock codes with these prefixes. Examples: '688' for STAR Market, '300' for ChiNext. Empty list means include all boards."
    )
    include_dragon_tiger: Optional[bool] = Field(
        default=False,
        description="Include only dragon-tiger list stocks (high institutional activity)"
    )
    target_count: Optional[int] = Field(
        default=30,
        description="Target number of stocks (max 500)",
        ge=1,
        le=500
    )
    sort_by: Optional[List[str]] = Field(
        default=None,
        description="Sort by these fields. Available: 'turnover', 'turnover_rate', 'market_cap', 'price', 'change_pct'. Default: ['turnover', 'turnover_rate', 'market_cap']"
    )


class StockInfo(BaseModel):
    """Stock information."""
    
    code: str = Field(..., description="Stock code")
    name: str = Field(..., description="Stock name")
    price: float = Field(..., description="Current price")
    market_cap: float = Field(..., description="Market cap in yuan")
    turnover: float = Field(..., description="Turnover in yuan")
    turnover_rate: float = Field(..., description="Turnover rate percentage")
    change_pct: float = Field(..., description="Change percentage")
    rank: Optional[int] = Field(None, description="Ranking position in current result set")
    score: Optional[float] = Field(None, description="Composite opportunity score")
    score_reason: Optional[str] = Field(None, description="Short explanation for the score")
    score_breakdown: Dict[str, float] = Field(default_factory=dict, description="Factor score breakdown")
    opportunity_tier: Optional[str] = Field(None, description="Opportunity tier such as A/S/B")
    open: Optional[float] = Field(None, description="Open price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")
    volume: Optional[float] = Field(None, description="Volume")
    amount: Optional[float] = Field(None, description="Amount")


class StockScreeningSummary(BaseModel):
    """Screening summary statistics."""
    
    count: int = Field(..., description="Number of filtered stocks")
    avg_market_cap: float = Field(..., description="Average market cap")
    avg_turnover: float = Field(..., description="Average turnover")
    avg_turnover_rate: float = Field(..., description="Average turnover rate")
    avg_price: float = Field(..., description="Average price")
    avg_change_pct: float = Field(..., description="Average change percentage")
    market: str = Field(..., description="Market region")
    data_mode: str = Field(..., description="Data mode")
    top_score: float = Field(0.0, description="Top candidate score")
    avg_score: float = Field(0.0, description="Average candidate score")
    top_candidates: List[str] = Field(default_factory=list, description="Top candidate codes")


class StockScreeningResponse(BaseModel):
    """Stock screening response."""
    
    stocks: List[StockInfo] = Field(..., description="Filtered stock list")
    summary: StockScreeningSummary = Field(..., description="Screening summary")


class ScreeningSnapshotSaveRequest(BaseModel):
    filters: StockScreeningRequest
    summary: StockScreeningSummary
    stocks: List[StockInfo]


class ScreeningSnapshotSaveResponse(BaseModel):
    success: bool
    snapshot_id: str
    record_id: int


class ScreeningSnapshotItem(BaseModel):
    snapshot_id: str
    market: str
    data_mode: str
    created_at: Optional[str] = None
    summary: dict = Field(default_factory=dict)
    performance_summary: dict = Field(default_factory=dict)


class ScreeningSnapshotListResponse(BaseModel):
    items: List[ScreeningSnapshotItem] = Field(default_factory=list)


class ScreeningTopAnalysisSummaryRequest(BaseModel):
    codes: List[str] = Field(default_factory=list, description="Top candidate codes")


class ScreeningTopAnalysisItem(BaseModel):
    code: str
    stock_name: Optional[str] = None
    operation_advice: Optional[str] = None
    trend_prediction: Optional[str] = None
    sentiment_score: Optional[int] = None
    analysis_summary: Optional[str] = None
    created_at: Optional[str] = None


class ScreeningTopAnalysisSummaryResponse(BaseModel):
    items: List[ScreeningTopAnalysisItem] = Field(default_factory=list)


class StockBatchAnalyzeRequest(BaseModel):
    """Request for batch stock analysis."""

    stocks: List[StockInfo] = Field(..., description="Stock list to analyze")
    report_type: str = Field(default="detailed", description="Report type: simple/detailed")


class StockBatchAnalyzeResponse(BaseModel):
    """Response for batch stock analysis."""

    task_ids: List[str] = Field(default_factory=list, description="Task IDs for submitted analyses")
    message: str = Field(default="批量分析任务已提交", description="Status message")
