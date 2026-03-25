# -*- coding: utf-8 -*-
"""Market data sync endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_market_data_sync_service
from api.v1.schemas.market_sync import (
    MarketSyncRunRequest,
    MarketSyncRunResponse,
    MarketSyncStatusResponse,
)
from src.services.market_data_sync_service import MarketDataSyncService

router = APIRouter()


@router.get(
    "/market-sync/status",
    response_model=MarketSyncStatusResponse,
    summary="Get market data sync status",
)
def get_market_sync_status(
    service: MarketDataSyncService = Depends(get_market_data_sync_service),
) -> MarketSyncStatusResponse:
    return MarketSyncStatusResponse(**service.get_status())


@router.post(
    "/market-sync/run",
    response_model=MarketSyncRunResponse,
    summary="Trigger market data sync",
)
def run_market_sync(
    request: MarketSyncRunRequest,
    service: MarketDataSyncService = Depends(get_market_data_sync_service),
) -> MarketSyncRunResponse:
    accepted = service.start_background_sync(request.markets or None)
    status = MarketSyncStatusResponse(**service.get_status())
    return MarketSyncRunResponse(
        accepted=accepted,
        message="sync started" if accepted else "sync already running",
        status=status,
    )
