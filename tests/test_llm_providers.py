# -*- coding: utf-8 -*-
"""Tests for extracted LLM provider helpers."""

import unittest
from types import SimpleNamespace

from src.llm.providers import build_openai_client_kwargs, init_openai_fallback


class _FakeOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class LlmProvidersTestCase(unittest.TestCase):
    def test_build_openai_client_kwargs_includes_optional_headers(self):
        config = SimpleNamespace(
            openai_api_key="sk-test-key",
            openai_base_url="https://aihubmix.com/v1",
        )

        kwargs = build_openai_client_kwargs(config)

        self.assertEqual(kwargs["api_key"], "sk-test-key")
        self.assertEqual(kwargs["base_url"], "https://aihubmix.com/v1")
        self.assertEqual(kwargs["default_headers"]["APP-Code"], "GPIJ3886")

    def test_init_openai_fallback_sets_client_and_flags(self):
        analyzer = SimpleNamespace(
            _openai_client=None,
            _current_model_name=None,
            _use_openai=False,
        )
        config = SimpleNamespace(
            openai_api_key="sk-test-key",
            openai_base_url="https://example.com/v1",
            openai_model="gpt-test",
        )

        init_openai_fallback(analyzer, config, openai_cls=_FakeOpenAI)

        self.assertIsNotNone(analyzer._openai_client)
        self.assertEqual(analyzer._current_model_name, "gpt-test")
        self.assertTrue(analyzer._use_openai)


if __name__ == "__main__":
    unittest.main()
