# -*- coding: utf-8 -*-
"""Tests for extracted analysis persistence service."""

import unittest
from datetime import date
from unittest.mock import Mock

from src.core.analysis_persistence import AnalysisPersistenceService


class AnalysisPersistenceServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.safe_to_dict = Mock(side_effect=lambda value: {"value": value} if value is not None else None)
        self.service = AnalysisPersistenceService(
            db=self.db,
            save_context_snapshot=True,
            safe_to_dict=self.safe_to_dict,
        )

    def test_has_today_data_delegates_to_db(self):
        today = date(2026, 3, 16)
        self.db.has_today_data.return_value = True

        result = self.service.has_today_data("600519", today)

        self.assertTrue(result)
        self.db.has_today_data.assert_called_once_with("600519", today)

    def test_build_context_snapshot_serializes_optional_objects(self):
        snapshot = self.service.build_context_snapshot(
            enhanced_context={"code": "600519"},
            news_content="headline",
            realtime_quote=object(),
            chip_data=None,
        )

        self.assertEqual(snapshot["enhanced_context"]["code"], "600519")
        self.assertEqual(snapshot["news_content"], "headline")
        self.assertIn("value", snapshot["realtime_quote_raw"])
        self.assertIsNone(snapshot["chip_distribution_raw"])

    def test_save_analysis_history_passes_save_snapshot_flag(self):
        result = Mock()

        self.service.save_analysis_history(
            result=result,
            query_id="q1",
            report_type="simple",
            news_content="news",
            context_snapshot={"ctx": True},
        )

        self.db.save_analysis_history.assert_called_once_with(
            result=result,
            query_id="q1",
            report_type="simple",
            news_content="news",
            context_snapshot={"ctx": True},
            save_snapshot=True,
        )

    def test_count_codes_with_today_data_counts_matching_rows(self):
        self.db.has_today_data.side_effect = [True, False, True]

        count = self.service.count_codes_with_today_data(["600519", "000001", "300750"], date(2026, 3, 16))

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
