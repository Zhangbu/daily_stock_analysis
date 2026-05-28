# -*- coding: utf-8 -*-
"""
Profile strategy backtest service for US profile workflows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from datetime import datetime
from typing import Dict, List, Literal, Optional

import pandas as pd
from sqlalchemy import and_, asc, delete, desc, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.services.profile_stock_metadata import get_profile_stock_metadata
from src.services.profile_strategy_service import ProfileStrategyService
from src.storage import ProfileBacktestResult, ProfileBacktestSummary, get_db


logger = logging.getLogger(__name__)


@dataclass
class ProfileBacktestItem:
    code: str
    stock_name: str
    analysis_date: date
    entry_date: date
    exit_date: date
    score: int
    grade: str
    verdict: str
    entry_price: float
    exit_price: float
    max_return_pct: float
    min_return_pct: float
    window_return_pct: float
    outcome: str


class ProfileStrategyBacktestService:
    """Run on-the-fly backtests for profile-based executable strategies."""

    def __init__(self, profile_name: str, strategy_name: str):
        self.profile_service = ProfileStrategyService(profile_name=profile_name, strategy_name=strategy_name)
        self.db = get_db()
        self.neutral_band_pct = 1.0
        self.warmup_bars = 60

    def run(
        self,
        *,
        stock_codes: Optional[List[str]] = None,
        analysis_date_from: Optional[date] = None,
        analysis_date_to: Optional[date] = None,
        eval_window_days: int = 10,
        only_passed: bool = True,
    ) -> Dict[str, object]:
        items: List[ProfileBacktestItem] = []
        resolved_codes = self.profile_service.resolve_stock_codes(stock_codes)

        for code in resolved_codes:
            df = self.profile_service.load_daily_data(code).copy()
            if df.empty or len(df) <= self.warmup_bars + eval_window_days:
                continue

            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
            stock_items = self._run_single_code(
                code=code,
                df=df,
                analysis_date_from=analysis_date_from,
                analysis_date_to=analysis_date_to,
                eval_window_days=eval_window_days,
                only_passed=only_passed,
            )
            items.extend(stock_items)

        items.sort(key=lambda item: (item.analysis_date, item.score), reverse=True)
        summary = self._build_summary(items, eval_window_days)
        self._persist_results(items, summary, eval_window_days)

        return {
            "profile_name": self.profile_service.profile.name,
            "strategy_name": self.profile_service.strategy.name,
            "display_name": self.profile_service.strategy.display_name,
            "eval_window_days": eval_window_days,
            "items": items,
            "summary": summary,
        }

    def get_persisted_results(
        self,
        *,
        analysis_date_from: Optional[date] = None,
        analysis_date_to: Optional[date] = None,
        code: Optional[str] = None,
        outcome: Optional[Literal["win", "loss", "neutral"]] = None,
        eval_window_days: Optional[int] = None,
        page: int = 1,
        limit: int = 50,
        sort_by: Literal["analysis_date", "score", "window_return_pct", "max_return_pct", "min_return_pct"] = "analysis_date",
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> Dict[str, object]:
        sort_column_map = {
            "analysis_date": ProfileBacktestResult.analysis_date,
            "score": ProfileBacktestResult.score,
            "window_return_pct": ProfileBacktestResult.window_return_pct,
            "max_return_pct": ProfileBacktestResult.max_return_pct,
            "min_return_pct": ProfileBacktestResult.min_return_pct,
        }
        if sort_by not in sort_column_map:
            raise ValueError(f"unsupported sort_by: {sort_by}")
        if sort_order not in {"asc", "desc"}:
            raise ValueError(f"unsupported sort_order: {sort_order}")

        conditions = [
            ProfileBacktestResult.profile_name == self.profile_service.profile.name,
            ProfileBacktestResult.strategy_name == self.profile_service.strategy.name,
        ]
        if code:
            conditions.append(ProfileBacktestResult.code == code.upper())
        if outcome:
            conditions.append(ProfileBacktestResult.outcome == outcome)
        if eval_window_days is not None:
            conditions.append(ProfileBacktestResult.eval_window_days == int(eval_window_days))
        if analysis_date_from is not None:
            conditions.append(ProfileBacktestResult.analysis_date >= analysis_date_from)
        if analysis_date_to is not None:
            conditions.append(ProfileBacktestResult.analysis_date <= analysis_date_to)

        offset = max(page - 1, 0) * limit
        primary_order = sort_column_map[sort_by]
        secondary_order = ProfileBacktestResult.analysis_date
        tertiary_order = ProfileBacktestResult.score
        order_fn = desc if sort_order == "desc" else asc

        with self.db.get_session() as session:
            total = session.execute(
                select(func.count(ProfileBacktestResult.id)).where(and_(*conditions))
            ).scalar() or 0
            rows = session.execute(
                select(ProfileBacktestResult)
                .where(and_(*conditions))
                .order_by(
                    order_fn(primary_order),
                    order_fn(secondary_order),
                    order_fn(tertiary_order),
                )
                .offset(offset)
                .limit(limit)
            ).scalars().all()

        items = [
            ProfileBacktestItem(
                code=row.code,
                stock_name=row.stock_name or row.code,
                analysis_date=row.analysis_date,
                entry_date=row.entry_date,
                exit_date=row.exit_date,
                score=int(row.score or 0),
                grade=row.grade,
                verdict=row.verdict or "",
                entry_price=float(row.entry_price or 0),
                exit_price=float(row.exit_price or 0),
                max_return_pct=float(row.max_return_pct or 0),
                min_return_pct=float(row.min_return_pct or 0),
                window_return_pct=float(row.window_return_pct or 0),
                outcome=row.outcome,
            )
            for row in rows
        ]
        return {
            "total": int(total),
            "page": page,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "items": items,
        }

    def get_persisted_summary(self, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, object]]:
        conditions = [
            ProfileBacktestSummary.profile_name == self.profile_service.profile.name,
            ProfileBacktestSummary.strategy_name == self.profile_service.strategy.name,
        ]
        if eval_window_days is not None:
            conditions.append(ProfileBacktestSummary.eval_window_days == int(eval_window_days))

        with self.db.get_session() as session:
            row = session.execute(
                select(ProfileBacktestSummary)
                .where(and_(*conditions))
                .order_by(desc(ProfileBacktestSummary.computed_at))
                .limit(1)
            ).scalar_one_or_none()

        if row is None:
            return None

        by_code = {}
        if row.by_code_json:
            try:
                import json
                parsed = json.loads(row.by_code_json)
                if isinstance(parsed, dict):
                    by_code = parsed
            except Exception:
                by_code = {}

        return {
            "total_signals": row.total_signals,
            "wins": row.wins,
            "losses": row.losses,
            "neutrals": row.neutrals,
            "win_rate_pct": row.win_rate_pct,
            "avg_return_pct": row.avg_return_pct,
            "avg_max_return_pct": row.avg_max_return_pct,
            "avg_min_return_pct": row.avg_min_return_pct,
            "eval_window_days": row.eval_window_days,
            "by_code": by_code,
        }

    def _run_single_code(
        self,
        *,
        code: str,
        df: pd.DataFrame,
        analysis_date_from: Optional[date],
        analysis_date_to: Optional[date],
        eval_window_days: int,
        only_passed: bool,
    ) -> List[ProfileBacktestItem]:
        items: List[ProfileBacktestItem] = []
        metadata = get_profile_stock_metadata(self.profile_service.profile.name, code)
        stock_name = metadata.name_zh if metadata else code

        last_entry_index = len(df) - eval_window_days - 1
        for idx in range(self.warmup_bars, last_entry_index + 1):
            signal_date = df.iloc[idx]["date"].date()
            if analysis_date_from and signal_date < analysis_date_from:
                continue
            if analysis_date_to and signal_date > analysis_date_to:
                continue

            signal_df = df.iloc[: idx + 1].copy()
            trend = self.profile_service.trend_analyzer.analyze(signal_df, code)
            signal = self.profile_service.signal_engine.evaluate(
                self.profile_service.strategy.name,
                signal_df,
                trend,
                self.profile_service.strategy.parameters,
            )
            if only_passed and not signal.passed:
                continue

            forward_df = df.iloc[idx + 1 : idx + 1 + eval_window_days].copy()
            if len(forward_df) < eval_window_days:
                continue

            entry_row = forward_df.iloc[0]
            exit_row = forward_df.iloc[-1]
            entry_price = float(entry_row["open"] if pd.notna(entry_row["open"]) else entry_row["close"])
            exit_price = float(exit_row["close"])
            max_high = float(forward_df["high"].max())
            min_low = float(forward_df["low"].min())
            window_return_pct = round((exit_price - entry_price) / entry_price * 100, 2)
            max_return_pct = round((max_high - entry_price) / entry_price * 100, 2)
            min_return_pct = round((min_low - entry_price) / entry_price * 100, 2)

            items.append(
                ProfileBacktestItem(
                    code=code,
                    stock_name=stock_name,
                    analysis_date=signal_date,
                    entry_date=entry_row["date"].date(),
                    exit_date=exit_row["date"].date(),
                    score=signal.score,
                    grade=signal.grade,
                    verdict=signal.verdict,
                    entry_price=round(entry_price, 4),
                    exit_price=round(exit_price, 4),
                    max_return_pct=max_return_pct,
                    min_return_pct=min_return_pct,
                    window_return_pct=window_return_pct,
                    outcome=self._resolve_outcome(window_return_pct),
                )
            )

        return items

    def _resolve_outcome(self, window_return_pct: float) -> str:
        if window_return_pct > self.neutral_band_pct:
            return "win"
        if window_return_pct < -self.neutral_band_pct:
            return "loss"
        return "neutral"

    def _build_summary(self, items: List[ProfileBacktestItem], eval_window_days: int) -> Dict[str, object]:
        total = len(items)
        wins = sum(1 for item in items if item.outcome == "win")
        losses = sum(1 for item in items if item.outcome == "loss")
        neutrals = sum(1 for item in items if item.outcome == "neutral")

        avg_return = round(sum(item.window_return_pct for item in items) / total, 2) if total else None
        avg_max_return = round(sum(item.max_return_pct for item in items) / total, 2) if total else None
        avg_min_return = round(sum(item.min_return_pct for item in items) / total, 2) if total else None
        win_rate = round(wins / total * 100, 2) if total else None

        by_code: Dict[str, Dict[str, object]] = {}
        grouped: Dict[str, List[ProfileBacktestItem]] = {}
        for item in items:
            grouped.setdefault(item.code, []).append(item)
        for code, rows in grouped.items():
            count = len(rows)
            code_wins = sum(1 for row in rows if row.outcome == "win")
            code_avg = round(sum(row.window_return_pct for row in rows) / count, 2) if count else None
            by_code[code] = {
                "stock_name": rows[0].stock_name,
                "signals": count,
                "win_rate_pct": round(code_wins / count * 100, 2) if count else None,
                "avg_return_pct": code_avg,
            }

        return {
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "neutrals": neutrals,
            "win_rate_pct": win_rate,
            "avg_return_pct": avg_return,
            "avg_max_return_pct": avg_max_return,
            "avg_min_return_pct": avg_min_return,
            "eval_window_days": eval_window_days,
            "by_code": by_code,
        }

    def _persist_results(self, items: List[ProfileBacktestItem], summary: Dict[str, object], eval_window_days: int) -> None:
        import json

        now = datetime.now()
        records = [
            {
                "profile_name": self.profile_service.profile.name,
                "strategy_name": self.profile_service.strategy.name,
                "code": item.code,
                "stock_name": item.stock_name,
                "analysis_date": item.analysis_date,
                "entry_date": item.entry_date,
                "exit_date": item.exit_date,
                "eval_window_days": int(eval_window_days),
                "score": item.score,
                "grade": item.grade,
                "verdict": item.verdict,
                "entry_price": item.entry_price,
                "exit_price": item.exit_price,
                "max_return_pct": item.max_return_pct,
                "min_return_pct": item.min_return_pct,
                "window_return_pct": item.window_return_pct,
                "outcome": item.outcome,
                "created_at": now,
                "updated_at": now,
            }
            for item in items
        ]

        def _write(session):
            session.execute(
                delete(ProfileBacktestResult).where(
                    and_(
                        ProfileBacktestResult.profile_name == self.profile_service.profile.name,
                        ProfileBacktestResult.strategy_name == self.profile_service.strategy.name,
                        ProfileBacktestResult.eval_window_days == int(eval_window_days),
                    )
                )
            )
            if records:
                stmt = sqlite_insert(ProfileBacktestResult).values(records)
                excluded = stmt.excluded
                session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[
                            "profile_name",
                            "strategy_name",
                            "code",
                            "analysis_date",
                            "eval_window_days",
                        ],
                        set_={
                            "stock_name": excluded.stock_name,
                            "entry_date": excluded.entry_date,
                            "exit_date": excluded.exit_date,
                            "score": excluded.score,
                            "grade": excluded.grade,
                            "verdict": excluded.verdict,
                            "entry_price": excluded.entry_price,
                            "exit_price": excluded.exit_price,
                            "max_return_pct": excluded.max_return_pct,
                            "min_return_pct": excluded.min_return_pct,
                            "window_return_pct": excluded.window_return_pct,
                            "outcome": excluded.outcome,
                            "updated_at": excluded.updated_at,
                        },
                    )
                )

            summary_stmt = sqlite_insert(ProfileBacktestSummary).values(
                {
                    "profile_name": self.profile_service.profile.name,
                    "strategy_name": self.profile_service.strategy.name,
                    "eval_window_days": int(eval_window_days),
                    "total_signals": int(summary["total_signals"]),
                    "wins": int(summary["wins"]),
                    "losses": int(summary["losses"]),
                    "neutrals": int(summary["neutrals"]),
                    "win_rate_pct": summary["win_rate_pct"],
                    "avg_return_pct": summary["avg_return_pct"],
                    "avg_max_return_pct": summary["avg_max_return_pct"],
                    "avg_min_return_pct": summary["avg_min_return_pct"],
                    "by_code_json": json.dumps(summary["by_code"], ensure_ascii=False),
                    "computed_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            excluded_summary = summary_stmt.excluded
            session.execute(
                summary_stmt.on_conflict_do_update(
                    index_elements=["profile_name", "strategy_name", "eval_window_days"],
                    set_={
                        "total_signals": excluded_summary.total_signals,
                        "wins": excluded_summary.wins,
                        "losses": excluded_summary.losses,
                        "neutrals": excluded_summary.neutrals,
                        "win_rate_pct": excluded_summary.win_rate_pct,
                        "avg_return_pct": excluded_summary.avg_return_pct,
                        "avg_max_return_pct": excluded_summary.avg_max_return_pct,
                        "avg_min_return_pct": excluded_summary.avg_min_return_pct,
                        "by_code_json": excluded_summary.by_code_json,
                        "computed_at": excluded_summary.computed_at,
                        "updated_at": excluded_summary.updated_at,
                    },
                )
            )
            return None

        self.db._run_write_transaction(
            f"profile_backtest[{self.profile_service.profile.name}:{self.profile_service.strategy.name}]",
            _write,
        )
