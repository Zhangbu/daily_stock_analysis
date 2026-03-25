# -*- coding: utf-8 -*-
"""Tests for storage compatibility exports."""

import unittest

from src.storage import DatabaseManager, StockDaily
from src.storage_database import DatabaseManager as ExportedDatabaseManager
from src.storage_models import StockDaily as ExportedStockDaily


class StorageExportTestCase(unittest.TestCase):
    def test_storage_database_exports_database_manager(self):
        self.assertIs(ExportedDatabaseManager, DatabaseManager)

    def test_storage_models_exports_stock_daily(self):
        self.assertIs(ExportedStockDaily, StockDaily)


if __name__ == "__main__":
    unittest.main()
