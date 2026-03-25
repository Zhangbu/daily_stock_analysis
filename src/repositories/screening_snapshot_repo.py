# -*- coding: utf-8 -*-
"""Repository for screening snapshots."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.storage import DatabaseManager, ScreeningSnapshot


class ScreeningSnapshotRepository:
    """Persistence facade for screening candidate pools."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_snapshot(
        self,
        *,
        snapshot_id: str,
        market: str,
        data_mode: str,
        filters: Dict[str, Any],
        summary: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> int:
        return self.db.save_screening_snapshot(
            snapshot_id=snapshot_id,
            market=market,
            data_mode=data_mode,
            filters=filters,
            summary=summary,
            candidates=candidates,
        )

    def get_recent(self, limit: int = 20) -> List[ScreeningSnapshot]:
        return self.db.get_recent_screening_snapshots(limit=limit)
