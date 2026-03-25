# -*- coding: utf-8 -*-
"""Tests for extracted LLM result parser helpers."""

import unittest

from src.analyzer import AnalysisResult
from src.llm.result_parser import fix_json_string, parse_response, parse_text_response


class LlmResultParserTestCase(unittest.TestCase):
    def test_fix_json_string_repairs_common_trailing_comma(self):
        repaired = fix_json_string('{"sentiment_score": 60,}')

        self.assertEqual(repaired, '{"sentiment_score": 60}')

    def test_parse_response_builds_structured_result(self):
        response_text = """
```json
{"sentiment_score": 72, "operation_advice": "买入", "analysis_summary": "strong", "dashboard": {"core_conclusion": {}}}
```
"""
        result = parse_response(response_text, "600519", "股票600519", AnalysisResult)

        self.assertEqual(result.sentiment_score, 72)
        self.assertEqual(result.operation_advice, "买入")
        self.assertEqual(result.decision_type, "buy")
        self.assertIsNotNone(result.dashboard)

    def test_parse_text_response_uses_keyword_fallback(self):
        result = parse_text_response("看多，建议买入，趋势强势突破", "600519", "贵州茅台", AnalysisResult)

        self.assertEqual(result.decision_type, "buy")
        self.assertEqual(result.trend_prediction, "看多")


if __name__ == "__main__":
    unittest.main()
