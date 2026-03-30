# -*- coding: utf-8 -*-
"""Tests for analyzer retry fast-fail policy."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.analyzer import GeminiAnalyzer, _is_non_retryable_llm_error


class AnalyzerRetryPolicyTestCase(unittest.TestCase):
    def test_non_retryable_error_classifier(self) -> None:
        self.assertTrue(_is_non_retryable_llm_error(UnboundLocalError("cannot access free variable x")))
        self.assertTrue(_is_non_retryable_llm_error(ValueError("Invalid API key provided")))
        self.assertFalse(_is_non_retryable_llm_error(RuntimeError("429 rate limit exceeded")))

    @patch("src.analyzer.get_config")
    def test_openai_call_fast_fails_for_non_retryable_error(self, mock_get_config: Mock) -> None:
        mock_get_config.return_value = SimpleNamespace(
            gemini_max_retries=5,
            gemini_retry_delay=0.1,
            openai_temperature=0.7,
        )
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer.SYSTEM_PROMPT = "system"
        analyzer._current_model_name = "gpt-4o-mini"
        analyzer._token_param_mode = {}
        analyzer._openai_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=Mock(side_effect=UnboundLocalError("cannot access free variable 'x'")),
                )
            )
        )

        with self.assertRaises(UnboundLocalError):
            analyzer._call_openai_api("hello", {"max_output_tokens": 128, "temperature": 0.3})

        self.assertEqual(analyzer._openai_client.chat.completions.create.call_count, 1)

    def test_prompt_compaction_trims_news_and_reason_lists(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._MAX_PROMPT_NEWS_CHARS = 1800
        analyzer._MAX_PROMPT_NEWS_LINES = 18
        analyzer._MAX_PROMPT_BULLET_ITEMS = 3
        analyzer._MAX_PROMPT_ITEM_CHARS = 90

        context = {
            "code": "600519",
            "date": "2026-03-30",
            "stock_name": "贵州茅台",
            "today": {"close": 1234.5, "open": 1220, "high": 1240, "low": 1218, "pct_chg": 1.2},
            "trend_analysis": {
                "trend_status": "多头趋势",
                "ma_alignment": "MA5>MA10>MA20",
                "trend_strength": 88,
                "bias_ma5": 1.5,
                "bias_ma10": 2.1,
                "volume_status": "放量",
                "volume_trend": "量价配合",
                "buy_signal": "买入",
                "signal_score": 82,
                "signal_reasons": ["A" * 120, "B" * 120, "C" * 120, "D" * 120],
                "risk_factors": ["R" * 120, "S" * 120, "T" * 120, "U" * 120],
            },
        }
        news_context = "\n".join(
            ["最新消息:"]
            + [f"  {i}. 标题{i}" for i in range(1, 8)]
            + ["     " + ("N" * 160) for _ in range(7)]
        )

        prompt = analyzer._format_prompt(context, "贵州茅台", news_context)

        self.assertNotIn("D" * 100, prompt)
        self.assertNotIn("U" * 100, prompt)
        self.assertNotIn("N" * 130, prompt)


if __name__ == "__main__":
    unittest.main()
