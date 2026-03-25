# -*- coding: utf-8 -*-
"""Tests for config schema export helpers."""

import unittest

from src.config import Config


class ConfigSchemaTestCase(unittest.TestCase):
    def test_grouped_fields_contains_expected_groups(self):
        config = Config()
        groups = config.grouped_fields()
        self.assertIn("ai", groups)
        self.assertIn("notification", groups)
        self.assertIn("runtime", groups)
        self.assertIn("market_data_cache_ttl", groups["runtime"])

    def test_export_schema_contains_group_items(self):
        config = Config(stock_list=["600519"], openai_api_key="secret")
        schema = config.export_schema()
        self.assertIn("groups", schema)
        self.assertIn("warnings", schema)
        ai_items = schema["groups"]["ai"]
        self.assertTrue(any(item["name"] == "openai_api_key" and item["is_secret"] for item in ai_items))
        runtime_items = schema["groups"]["runtime"]
        self.assertTrue(any(item["name"] == "observability_warn_latency_ms" for item in runtime_items))


if __name__ == "__main__":
    unittest.main()
