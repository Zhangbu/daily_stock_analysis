# -*- coding: utf-8 -*-
"""Signal strategy backtest endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.strategy_backtest import (
    StrategySignalBacktestRunRequest,
    StrategySignalBacktestRunResponse,
    StrategySignalInfo,
    StrategySignalListResponse,
)
from src.services.strategy_signal_backtest_service import StrategySignalBacktestService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/strategies",
    response_model=StrategySignalListResponse,
    responses={200: {"description": "Signal backtest strategies"}},
    summary="Get signal backtest strategies",
)
def get_signal_backtest_strategies() -> StrategySignalListResponse:
    service = StrategySignalBacktestService()
    strategies = [StrategySignalInfo(**item) for item in service.list_strategies()]
    return StrategySignalListResponse(strategies=strategies)


@router.post(
    "/run",
    response_model=StrategySignalBacktestRunResponse,
    responses={
        200: {"description": "Signal backtest completed"},
        400: {"description": "Bad request", "model": ErrorResponse},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Run signal strategy backtest",
)
def run_signal_strategy_backtest(
    request: StrategySignalBacktestRunRequest,
) -> StrategySignalBacktestRunResponse:
    try:
        service = StrategySignalBacktestService()
        payload = service.run_backtest(
            code=request.code,
            strategy_ids=request.strategy_ids,
            days=request.days,
            initial_capital=request.initial_capital,
        )
        return StrategySignalBacktestRunResponse(**payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_request", "message": str(exc)},
        )
    except Exception as exc:
        logger.error("Signal strategy backtest failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"信号回测失败: {str(exc)}"},
        )
