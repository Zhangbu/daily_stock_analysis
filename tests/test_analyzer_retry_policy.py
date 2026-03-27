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


if __name__ == "__main__":
    unittest.main()
