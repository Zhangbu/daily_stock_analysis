# -*- coding: utf-8 -*-
"""
===================================
Stock Screening API
===================================
"""

import logging
import uuid
import json

from fastapi import APIRouter, HTTPException

from api.v1.schemas.screening import (
    ScreeningSnapshotItem,
    ScreeningSnapshotListResponse,
    ScreeningSnapshotSaveRequest,
    ScreeningSnapshotSaveResponse,
    ScreeningTopAnalysisItem,
    ScreeningTopAnalysisSummaryRequest,
    ScreeningTopAnalysisSummaryResponse,
    StockScreeningRequest,
    StockScreeningResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.repositories.analysis_repo import AnalysisRepository
from src.repositories.screening_snapshot_repo import ScreeningSnapshotRepository
from src.repositories.stock_repo import StockRepository
from src.services.screening_service import ScreeningService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/filter",
    response_model=StockScreeningResponse,
    responses={
        200: {"description": "Screening results"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Screen stocks based on criteria",
    description="Filter stocks based on multiple criteria including market cap, turnover, price, and change percentage"
)
def screen_stocks(request: StockScreeningRequest) -> StockScreeningResponse:
    """
    Screen stocks based on multiple criteria.
    
    Args:
        request: Stock screening request parameters
        
    Returns:
        StockScreeningResponse: Filtered stocks and summary statistics
    """
    try:
        service = ScreeningService()
        
        # Call screening service
        result = service.screen_stocks(
            market=request.market,
            data_mode=request.data_mode,
            min_market_cap=request.min_market_cap,
            max_market_cap=request.max_market_cap,
            min_turnover=request.min_turnover,
            min_turnover_rate=request.min_turnover_rate,
            max_turnover_rate=request.max_turnover_rate,
            min_price=request.min_price,
            max_price=request.max_price,
            min_change_pct=request.min_change_pct,
            max_change_pct=request.max_change_pct,
            exclude_st=request.exclude_st,
            exclude_prefixes=request.exclude_prefixes,
            include_dragon_tiger=request.include_dragon_tiger,
            target_count=request.target_count,
            sort_by=request.sort_by
        )
        
        # Convert to response model
        stocks_data = [
            {
                'code': stock['code'],
                'name': stock['name'],
                'price': stock['price'],
                'market_cap': stock['market_cap'],
                'turnover': stock['turnover'],
                'turnover_rate': stock['turnover_rate'],
                'change_pct': stock['change_pct'],
                'rank': stock.get('rank'),
                'score': stock.get('score'),
                'score_reason': stock.get('score_reason'),
                'score_breakdown': stock.get('score_breakdown') or {},
                'opportunity_tier': stock.get('opportunity_tier'),
                'open': stock.get('open'),
                'high': stock.get('high'),
                'low': stock.get('low'),
                'volume': stock.get('volume'),
                'amount': stock.get('amount'),
            }
            for stock in result['stocks']
        ]
        
        summary_data = {
            'count': result['summary']['count'],
            'avg_market_cap': result['summary']['avg_market_cap'],
            'avg_turnover': result['summary']['avg_turnover'],
            'avg_turnover_rate': result['summary']['avg_turnover_rate'],
            'avg_price': result['summary']['avg_price'],
            'avg_change_pct': result['summary']['avg_change_pct'],
            'market': result['summary']['market'],
            'data_mode': result['summary']['data_mode'],
            'top_score': result['summary'].get('top_score', 0.0),
            'avg_score': result['summary'].get('avg_score', 0.0),
            'top_candidates': result['summary'].get('top_candidates', []),
        }
        
        return StockScreeningResponse(
            stocks=stocks_data,
            summary=summary_data
        )
        
    except Exception as e:
        logger.error(f"Stock screening failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Stock screening failed: {str(e)}"
            }
        )


@router.post(
    "/snapshot",
    response_model=ScreeningSnapshotSaveResponse,
    summary="Save screening snapshot",
)
def save_screening_snapshot(request: ScreeningSnapshotSaveRequest) -> ScreeningSnapshotSaveResponse:
    repo = ScreeningSnapshotRepository()
    snapshot_id = uuid.uuid4().hex
    record_id = repo.save_snapshot(
        snapshot_id=snapshot_id,
        market=request.summary.market,
        data_mode=request.summary.data_mode,
        filters=request.filters.model_dump(),
        summary=request.summary.model_dump(),
        candidates=[item.model_dump() for item in request.stocks],
    )
    if record_id <= 0:
        raise HTTPException(
            status_code=500,
            detail={"error": "snapshot_save_failed", "message": "Failed to save screening snapshot"},
        )
    return ScreeningSnapshotSaveResponse(success=True, snapshot_id=snapshot_id, record_id=record_id)


@router.get(
    "/snapshots",
    response_model=ScreeningSnapshotListResponse,
    summary="List recent screening snapshots",
)
def list_screening_snapshots(limit: int = 20) -> ScreeningSnapshotListResponse:
    repo = ScreeningSnapshotRepository()
    stock_repo = StockRepository()
    rows = repo.get_recent(limit=limit)
    items = []
    for row in rows:
        summary = json.loads(row.summary_json) if row.summary_json else {}
        candidates = json.loads(row.candidates_json) if row.candidates_json else []
        codes = [str(item.get("code", "")).upper() for item in candidates if item.get("code")]
        latest_rows = {str(item.code).upper(): item for item in stock_repo.get_latest_snapshots() if str(item.code).upper() in codes}
        returns = []
        for candidate in candidates[:5]:
            code = str(candidate.get("code", "")).upper()
            base_price = float(candidate.get("price") or 0.0)
            latest = latest_rows.get(code)
            latest_close = float(getattr(latest, "close", 0.0) or 0.0)
            if base_price > 0 and latest_close > 0:
                returns.append(((latest_close - base_price) / base_price) * 100)
        performance_summary = {
            "tracked_count": len(returns),
            "avg_return_pct": round(sum(returns) / len(returns), 2) if returns else 0.0,
            "positive_count": sum(1 for value in returns if value > 0),
        }
        items.append(
            ScreeningSnapshotItem(
                snapshot_id=row.snapshot_id,
                market=row.market,
                data_mode=row.data_mode,
                created_at=row.created_at.isoformat() if row.created_at else None,
                summary=summary,
                performance_summary=performance_summary,
            )
        )
    return ScreeningSnapshotListResponse(items=items)


@router.post(
    "/top-analysis-summary",
    response_model=ScreeningTopAnalysisSummaryResponse,
    summary="Get top analysis summary",
)
def get_top_analysis_summary(
    request: ScreeningTopAnalysisSummaryRequest,
) -> ScreeningTopAnalysisSummaryResponse:
    repo = AnalysisRepository()
    rows = repo.get_latest_by_codes(request.codes[:10])
    items = []
    for code in request.codes[:10]:
        row = rows.get(str(code).upper())
        if row is None:
            continue
        items.append(
            ScreeningTopAnalysisItem(
                code=row.code,
                stock_name=row.name,
                operation_advice=row.operation_advice,
                trend_prediction=row.trend_prediction,
                sentiment_score=row.sentiment_score,
                analysis_summary=row.analysis_summary,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
        )
    return ScreeningTopAnalysisSummaryResponse(items=items)
