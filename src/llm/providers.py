# -*- coding: utf-8 -*-
"""Provider-specific LLM initialization helpers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_valid_gemini_key(key: Optional[str]) -> bool:
    """Check whether a Gemini API key looks usable."""
    return bool(key and not key.startswith("your_") and len(key) > 10)


def collect_gemini_api_keys(config, primary_key: Optional[str] = None) -> List[str]:
    """Build a de-duplicated Gemini API key pool from config and optional primary key."""
    keys: List[str] = []

    def _push(candidate: Optional[str]) -> None:
        if not _is_valid_gemini_key(candidate):
            return
        value = candidate.strip()
        if value and value not in keys:
            keys.append(value)

    _push(primary_key)
    for item in getattr(config, "gemini_api_keys", []) or []:
        _push(item)
    _push(getattr(config, "gemini_api_key", None))
    return keys



def build_openai_client_kwargs(config) -> Dict[str, Any]:
    """Build OpenAI-compatible client kwargs from config."""
    client_kwargs = {"api_key": config.openai_api_key}
    if config.openai_base_url and config.openai_base_url.startswith("http"):
        client_kwargs["base_url"] = config.openai_base_url
    if config.openai_base_url and "aihubmix.com" in config.openai_base_url:
        client_kwargs["default_headers"] = {"APP-Code": "GPIJ3886"}
    return client_kwargs


def init_anthropic_fallback(analyzer, config) -> None:
    """Initialize Anthropic Claude as a fallback provider."""
    anthropic_key_valid = (
        config.anthropic_api_key
        and not config.anthropic_api_key.startswith("your_")
        and len(config.anthropic_api_key) > 10
    )
    if not anthropic_key_valid:
        logger.debug("Anthropic API Key not configured or invalid")
        return
    try:
        from anthropic import Anthropic

        analyzer._anthropic_client = Anthropic(api_key=config.anthropic_api_key)
        analyzer._current_model_name = config.anthropic_model
        analyzer._use_anthropic = True
        logger.info(f"Anthropic Claude API init OK (model: {config.anthropic_model})")
    except ImportError:
        logger.error("anthropic package not installed, run: pip install anthropic")
    except Exception as exc:
        logger.error(f"Anthropic API init failed: {exc}")


def init_openai_fallback(analyzer, config, openai_cls: Optional[type] = None) -> None:
    """Initialize an OpenAI-compatible client as a fallback provider."""
    openai_key_valid = (
        config.openai_api_key
        and not config.openai_api_key.startswith("your_")
        and len(config.openai_api_key) >= 8
    )
    if not openai_key_valid:
        logger.debug("OpenAI 兼容 API 未配置或配置无效")
        return

    try:
        if openai_cls is None:
            from openai import OpenAI as openai_cls
    except ImportError:
        logger.error("未安装 openai 库，请运行: pip install openai")
        return

    try:
        analyzer._openai_client = openai_cls(**build_openai_client_kwargs(config))
        analyzer._current_model_name = config.openai_model
        analyzer._use_openai = True
        logger.info(
            f"OpenAI 兼容 API 初始化成功 (base_url: {config.openai_base_url}, model: {config.openai_model})"
        )
    except ImportError as exc:
        if "socksio" in str(exc).lower() or "socks" in str(exc).lower():
            logger.error("OpenAI 客户端需要 SOCKS 代理支持，请运行: pip install httpx[socks] 或 pip install socksio")
        else:
            logger.error(f"OpenAI 依赖缺失: {exc}")
    except Exception as exc:
        error_msg = str(exc).lower()
        if "socks" in error_msg or "socksio" in error_msg or "proxy" in error_msg:
            logger.error(f"OpenAI 代理配置错误: {exc}，如使用 SOCKS 代理请运行: pip install httpx[socks]")
        else:
            logger.error(f"OpenAI 兼容 API 初始化失败: {exc}")


def init_gemini_model(analyzer, config, genai_module=None) -> None:
    """Initialize the primary Gemini model with fallback support."""
    try:
        if genai_module is None:
            import google.generativeai as genai_module

        genai_module.configure(api_key=analyzer._api_key)

        model_name = config.gemini_model
        fallback_model = config.gemini_model_fallback
        try:
            analyzer._model = genai_module.GenerativeModel(
                model_name=model_name,
                system_instruction=analyzer.SYSTEM_PROMPT,
            )
            analyzer._current_model_name = model_name
            analyzer._using_fallback = False
            logger.info(f"Gemini 模型初始化成功 (模型: {model_name})")
        except Exception as model_error:
            logger.warning(f"主模型 {model_name} 初始化失败: {model_error}，尝试备选模型 {fallback_model}")
            analyzer._model = genai_module.GenerativeModel(
                model_name=fallback_model,
                system_instruction=analyzer.SYSTEM_PROMPT,
            )
            analyzer._current_model_name = fallback_model
            analyzer._using_fallback = True
            logger.info(f"Gemini 备选模型初始化成功 (模型: {fallback_model})")
    except Exception as exc:
        logger.error(f"Gemini 模型初始化失败: {exc}")
        analyzer._model = None


def switch_to_gemini_fallback_model(analyzer, config, genai_module=None) -> bool:
    """Switch the analyzer to the configured Gemini fallback model."""
    try:
        if genai_module is None:
            import google.generativeai as genai_module

        fallback_model = config.gemini_model_fallback
        logger.warning(f"[LLM] 切换到备选模型: {fallback_model}")
        analyzer._model = genai_module.GenerativeModel(
            model_name=fallback_model,
            system_instruction=analyzer.SYSTEM_PROMPT,
        )
        analyzer._current_model_name = fallback_model
        analyzer._using_fallback = True
        logger.info(f"[LLM] 备选模型 {fallback_model} 初始化成功")
        return True
    except Exception as exc:
        logger.error(f"[LLM] 切换备选模型失败: {exc}")
        return False
