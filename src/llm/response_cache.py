# -*- coding: utf-8 -*-
"""
===================================
LLM 响应缓存模块
===================================

设计目标：
1. 避免重复分析相同股票 + 相同日期
2. 支持内存缓存（可选 Redis 扩展）
3. 可配置的 TTL 和清理策略

使用场景：
- 相同股票当日重复分析
- 测试/调试时避免重复调用 API
- 断点续分析
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class LLMResponseCache:
    """
    LLM 响应缓存

    功能：
    1. 内存缓存 - 快速访问
    2. 持久化缓存 - 进程重启后仍然有效
    3. 自动清理 - 定期删除过期缓存

    缓存键构成：code + prompt_hash + model_name
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        cache_file: Optional[Path] = None,
        max_cache_size: int = 1000
    ):
        """
        初始化缓存

        Args:
            ttl_hours: 缓存有效期（小时），默认 24 小时
            cache_file: 持久化缓存文件路径
            max_cache_size: 最大缓存条目数
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(hours=ttl_hours)
        self._max_size = max_cache_size

        # 持久化缓存文件
        if cache_file is None:
            cache_file = Path(__file__).parent.parent.parent / "data" / "llm_response_cache.json"
        self._cache_file = cache_file

        # 加载持久化缓存
        self._load_cache()

    def _make_key(self, code: str, prompt_hash: str, model: str) -> str:
        """生成缓存键"""
        return f"{code}:{prompt_hash}:{model}"

    def _hash_prompt(self, prompt: str) -> str:
        """对 prompt 进行 MD5 哈希"""
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()

    def _load_cache(self) -> None:
        """从文件加载缓存"""
        if not self._cache_file.exists():
            return

        try:
            with open(self._cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 加载时过滤过期缓存
            now = datetime.now()
            for key, entry in data.items():
                timestamp = datetime.fromisoformat(entry['timestamp'])
                if now - timestamp < self._ttl:
                    self._cache[key] = {
                        'response': entry['response'],
                        'timestamp': timestamp
                    }

            logger.info(f"Loaded {len(self._cache)} cache entries from {self._cache_file}")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            # 确保目录存在
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)

            # 序列化缓存
            data = {}
            for key, entry in self._cache.items():
                data[key] = {
                    'response': entry['response'],
                    'timestamp': entry['timestamp'].isoformat()
                }

            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved {len(self._cache)} cache entries to {self._cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def get(self, code: str, prompt: str, model: str) -> Optional[str]:
        """
        获取缓存的响应

        Args:
            code: 股票代码
            prompt: 原始 prompt
            model: 模型名称

        Returns:
            缓存的响应文本，如果未命中则返回 None
        """
        key = self._make_key(code, self._hash_prompt(prompt), model)

        if key not in self._cache:
            return None

        entry = self._cache[key]
        elapsed = datetime.now() - entry['timestamp']

        # 检查是否过期
        if elapsed >= self._ttl:
            del self._cache[key]
            logger.debug(f"[{code}] Cache expired (age: {elapsed})")
            return None

        # 检查是否需要清理（LRU 策略）
        if len(self._cache) > self._max_size:
            self._cleanup_lru()

        logger.debug(f"[{code}] Cache hit (age: {elapsed})")
        return entry['response']

    def set(self, code: str, prompt: str, model: str, response: str) -> None:
        """
        缓存响应

        Args:
            code: 股票代码
            prompt: 原始 prompt
            model: 模型名称
            response: LLM 响应文本
        """
        key = self._make_key(code, self._hash_prompt(prompt), model)

        # 如果缓存已满，先清理
        if len(self._cache) >= self._max_size:
            self._cleanup_lru()

        self._cache[key] = {
            'response': response,
            'timestamp': datetime.now()
        }

        # 定期保存到文件（每 10 条保存一次）
        if len(self._cache) % 10 == 0:
            self._save_cache()

        logger.debug(f"[{code}] Cached response")

    def _cleanup_lru(self) -> int:
        """清理最久未使用的缓存（保留最近的 80%）"""
        if not self._cache:
            return 0

        # 按时间排序
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k]['timestamp']
        )

        # 删除最老的 20%
        remove_count = max(1, len(self._cache) // 5)
        removed = 0
        for key in sorted_keys[:remove_count]:
            del self._cache[key]
            removed += 1

        logger.debug(f"Cleaned up {removed} LRU cache entries")
        return removed

    def clear_expired(self) -> int:
        """清理所有过期缓存"""
        now = datetime.now()
        expired = [
            k for k, v in self._cache.items()
            if now - v['timestamp'] >= self._ttl
        ]
        for k in expired:
            del self._cache[k]

        if expired:
            self._save_cache()
            logger.info(f"Cleaned up {len(expired)} expired cache entries")

        return len(expired)

    def clear_all(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        self._save_cache()
        logger.info("Cleared all cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        now = datetime.now()
        ages = [(now - v['timestamp']).total_seconds() / 3600 for v in self._cache.values()]

        return {
            'total_entries': len(self._cache),
            'avg_age_hours': sum(ages) / len(ages) if ages else 0,
            'max_age_hours': max(ages) if ages else 0,
            'ttl_hours': self._ttl.total_seconds() / 3600,
            'cache_file': str(self._cache_file),
        }

    def delete(self, code: str) -> int:
        """删除指定股票的所有缓存"""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"{code}:")]
        for k in keys_to_delete:
            del self._cache[k]

        if keys_to_delete:
            self._save_cache()
            logger.info(f"Deleted {len(keys_to_delete)} cache entries for {code}")

        return len(keys_to_delete)


# 全局缓存实例
_llm_cache: Optional[LLMResponseCache] = None


def get_llm_cache(ttl_hours: Optional[int] = None) -> LLMResponseCache:
    """获取全局 LLM 缓存实例"""
    global _llm_cache
    if _llm_cache is None:
        # 从环境变量读取配置（优先）或从 Config 对象读取
        if ttl_hours is None:
            ttl = int(os.getenv('LLM_CACHE_TTL_HOURS', '24'))
        else:
            ttl = ttl_hours
        max_size = int(os.getenv('LLM_CACHE_MAX_SIZE', '1000'))
        _llm_cache = LLMResponseCache(ttl_hours=ttl, max_cache_size=max_size)
    return _llm_cache


def invalidate_cache_for_stock(code: str) -> int:
    """使指定股票的缓存失效"""
    cache = get_llm_cache()
    return cache.delete(code)


def clear_llm_cache() -> None:
    """清空所有 LLM 缓存"""
    cache = get_llm_cache()
    cache.clear_all()


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    cache = get_llm_cache()
    return cache.get_stats()
