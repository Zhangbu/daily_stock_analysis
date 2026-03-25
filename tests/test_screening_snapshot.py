# -*- coding: utf-8 -*-
"""Tests for screening snapshot persistence."""

import os
import tempfile
import unittest

from src.config import Config
from src.storage import DatabaseManager


class ScreeningSnapshotTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_screening_snapshot.db")
        os.environ["DATABASE_PATH"] = self._db_path
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self._temp_dir.cleanup()

    def test_save_and_list_screening_snapshot(self) -> None:
        record_id = self.db.save_screening_snapshot(
            snapshot_id="snap_001",
            market="cn",
            data_mode="database",
            filters={"market": "cn"},
            summary={"top_candidates": ["600519"], "top_score": 88},
            candidates=[{"code": "600519", "score": 88}],
        )

        self.assertGreater(record_id, 0)

        rows = self.db.get_recent_screening_snapshots(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].snapshot_id, "snap_001")
        self.assertEqual(rows[0].market, "cn")


if __name__ == "__main__":
    unittest.main()
