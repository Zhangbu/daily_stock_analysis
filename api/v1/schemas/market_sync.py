# -*- coding: utf-8 -*-
"""Market data sync API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MarketSyncRunRequest(BaseModel):
    markets: List[str] = Field(default_factory=list, description="Markets to sync: cn/us")


class MarketSyncStatusResponse(BaseModel):
    running: bool
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    current_market: Optional[str] = None
    current_code: Optional[str] = None
    processed: int
    saved: int
    skipped: int
    errors: int
    total_candidates: int
    priority_candidates: int
    priority_processed: int
    priority_completed: int
    message: str
    markets: List[str] = Field(default_factory=list)


class MarketSyncRunResponse(BaseModel):
    accepted: bool
    message: str
    status: MarketSyncStatusResponse
