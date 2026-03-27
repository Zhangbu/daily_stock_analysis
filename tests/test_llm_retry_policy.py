# -*- coding: utf-8 -*-
"""Tests for shared LLM retry policy helpers."""

import unittest

from src.llm.retry_policy import (
    clip_text,
    first_non_ascii_info,
    is_ascii_encode_error,
    is_non_retryable_llm_error,
    safe_exception_text,
)


class LLMRetryPolicyTestCase(unittest.TestCase):
    def test_ascii_encode_error_detection(self) -> None:
        self.assertTrue(is_ascii_encode_error("'ascii' codec can't encode character x: ordinal not in range(128)"))
        self.assertFalse(is_ascii_encode_error("429 rate limit exceeded"))

    def test_non_retryable_classifier(self) -> None:
        self.assertTrue(is_non_retryable_llm_error(UnboundLocalError("cannot access free variable x")))
        self.assertTrue(is_non_retryable_llm_error(ValueError("invalid api key")))
        self.assertFalse(is_non_retryable_llm_error(RuntimeError("429 rate limit")))

    def test_first_non_ascii_info(self) -> None:
        self.assertEqual(first_non_ascii_info("abc"), None)
        info = first_non_ascii_info("ab中")
        self.assertIsNotNone(info)
        self.assertEqual(info[0], 2)

    def test_safe_exception_text_and_clip(self) -> None:
        msg = safe_exception_text(ValueError("bad字符"))
        self.assertIn("\\u", msg)
        self.assertEqual(clip_text("abc", limit=5), "abc")
        self.assertEqual(clip_text("abcdef", limit=3), "abc...")


if __name__ == "__main__":
    unittest.main()
