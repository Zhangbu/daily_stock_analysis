# -*- coding: utf-8 -*-
"""Search provider adapters."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from itertools import cycle
from typing import Any, Dict, List, Optional

import requests
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.search.content_fetcher import fetch_url_content
from src.search.types import SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_SEARCH_TRANSIENT_EXCEPTIONS = (
    requests.exceptions.SSLError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(_SEARCH_TRANSIENT_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _post_with_retry(url: str, *, headers: Dict[str, str], json: Dict[str, Any], timeout: int) -> requests.Response:
    """POST with retry on transient SSL/network errors."""
    return requests.post(url, headers=headers, json=json, timeout=timeout)


class BaseSearchProvider(ABC):
    """搜索引擎基类"""

    def __init__(self, api_keys: List[str], name: str):
        self._api_keys = api_keys
        self._name = name
        self._key_cycle = cycle(api_keys) if api_keys else None
        self._key_usage: Dict[str, int] = {key: 0 for key in api_keys}
        self._key_errors: Dict[str, int] = {key: 0 for key in api_keys}

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return bool(self._api_keys)

    def _get_next_key(self) -> Optional[str]:
        if not self._key_cycle:
            return None

        for _ in range(len(self._api_keys)):
            key = next(self._key_cycle)
            if self._key_errors.get(key, 0) < 3:
                return key

        logger.warning(f"[{self._name}] 所有 API Key 都有错误记录，重置错误计数")
        self._key_errors = {key: 0 for key in self._api_keys}
        return self._api_keys[0] if self._api_keys else None

    def _record_success(self, key: str) -> None:
        self._key_usage[key] = self._key_usage.get(key, 0) + 1
        if key in self._key_errors and self._key_errors[key] > 0:
            self._key_errors[key] -= 1

    def _record_error(self, key: str) -> None:
        self._key_errors[key] = self._key_errors.get(key, 0) + 1
        logger.warning(f"[{self._name}] API Key {key[:8]}... 错误计数: {self._key_errors[key]}")

    @abstractmethod
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行搜索（子类实现）"""

    def search(self, query: str, max_results: int = 5, days: int = 7) -> SearchResponse:
        api_key = self._get_next_key()
        if not api_key:
            return SearchResponse(
                query=query,
                results=[],
                provider=self._name,
                success=False,
                error_message=f"{self._name} 未配置 API Key",
            )

        start_time = time.time()
        try:
            response = self._do_search(query, api_key, max_results, days=days)
            response.search_time = time.time() - start_time

            if response.success:
                self._record_success(api_key)
                logger.info(
                    f"[{self._name}] 搜索 '{query}' 成功，返回 {len(response.results)} 条结果，耗时 {response.search_time:.2f}s"
                )
            else:
                self._record_error(api_key)

            return response

        except Exception as exc:
            self._record_error(api_key)
            elapsed = time.time() - start_time
            logger.error(f"[{self._name}] 搜索 '{query}' 失败: {exc}")
            return SearchResponse(
                query=query,
                results=[],
                provider=self._name,
                success=False,
                error_message=str(exc),
                search_time=elapsed,
            )


class TavilySearchProvider(BaseSearchProvider):
    """Tavily 搜索引擎。"""

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys, "Tavily")

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        try:
            from tavily import TavilyClient
        except ImportError:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message="tavily-python 未安装，请运行: pip install tavily-python",
            )

        try:
            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
                days=days,
            )

            logger.info(f"[Tavily] 搜索完成，query='{query}', 返回 {len(response.get('results', []))} 条结果")
            logger.debug(f"[Tavily] 原始响应: {response}")

            results = []
            for item in response.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("content", "")[:500],
                        url=item.get("url", ""),
                        source=self._extract_domain(item.get("url", "")),
                        published_date=item.get("published_date"),
                    )
                )

            return SearchResponse(query=query, results=results, provider=self.name, success=True)

        except Exception as exc:
            error_msg = str(exc)
            if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                error_msg = f"API 配额已用尽: {error_msg}"

            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=error_msg,
            )

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain or "未知来源"
        except Exception:
            return "未知来源"


class SerpAPISearchProvider(BaseSearchProvider):
    """SerpAPI 搜索引擎。"""

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys, "SerpAPI")

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        try:
            from serpapi import GoogleSearch
        except ImportError:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message="google-search-results 未安装，请运行: pip install google-search-results",
            )

        try:
            tbs = "qdr:w"
            if days <= 1:
                tbs = "qdr:d"
            elif days <= 7:
                tbs = "qdr:w"
            elif days <= 30:
                tbs = "qdr:m"
            else:
                tbs = "qdr:y"

            params = {
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "google_domain": "google.com.hk",
                "hl": "zh-cn",
                "gl": "cn",
                "tbs": tbs,
                "num": max_results,
            }

            search = GoogleSearch(params)
            response = search.get_dict()
            logger.debug(f"[SerpAPI] 原始响应 keys: {response.keys()}")
            results = []

            kg = response.get("knowledge_graph", {})
            if kg:
                title = kg.get("title", "知识图谱")
                desc = kg.get("description", "")
                details = []
                for key in ["type", "founded", "headquarters", "employees", "ceo"]:
                    val = kg.get(key)
                    if val:
                        details.append(f"{key}: {val}")

                snippet = f"{desc}\n" + " | ".join(details) if details else desc
                results.append(
                    SearchResult(
                        title=f"[知识图谱] {title}",
                        snippet=snippet,
                        url=kg.get("source", {}).get("link", ""),
                        source="Google Knowledge Graph",
                    )
                )

            ab = response.get("answer_box", {})
            if ab:
                ab_title = ab.get("title", "精选回答")
                ab_snippet = ""
                if ab.get("type") == "finance_results":
                    stock = ab.get("stock", "")
                    price = ab.get("price", "")
                    currency = ab.get("currency", "")
                    movement = ab.get("price_movement", {})
                    mv_val = movement.get("percentage", 0)
                    mv_dir = movement.get("movement", "")
                    ab_title = f"[行情卡片] {stock}"
                    ab_snippet = f"价格: {price} {currency}\n涨跌: {mv_dir} {mv_val}%"
                    if "table" in ab:
                        table_data = []
                        for row in ab["table"]:
                            if "name" in row and "value" in row:
                                table_data.append(f"{row['name']}: {row['value']}")
                        if table_data:
                            ab_snippet += "\n" + "; ".join(table_data)
                elif "snippet" in ab:
                    ab_snippet = ab.get("snippet", "")
                    list_items = ab.get("list", [])
                    if list_items:
                        ab_snippet += "\n" + "\n".join([f"- {item}" for item in list_items])
                elif "answer" in ab:
                    ab_snippet = ab.get("answer", "")

                if ab_snippet:
                    results.append(
                        SearchResult(
                            title=f"[精选回答] {ab_title}",
                            snippet=ab_snippet,
                            url=ab.get("link", "") or ab.get("displayed_link", ""),
                            source="Google Answer Box",
                        )
                    )

            for rq in response.get("related_questions", [])[:3]:
                question = rq.get("question", "")
                snippet = rq.get("snippet", "")
                link = rq.get("link", "")
                if question and snippet:
                    results.append(
                        SearchResult(
                            title=f"[相关问题] {question}",
                            snippet=snippet,
                            url=link,
                            source="Google Related Questions",
                        )
                    )

            for item in response.get("organic_results", [])[:max_results]:
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                if link:
                    try:
                        fetched_content = fetch_url_content(link, timeout=5)
                        if fetched_content:
                            if len(fetched_content) > 500:
                                snippet = f"{snippet}\n\n【网页详情】\n{fetched_content[:500]}..."
                            else:
                                snippet = f"{snippet}\n\n【网页详情】\n{fetched_content}"
                    except Exception as exc:
                        logger.debug(f"[SerpAPI] Fetch content failed: {exc}")

                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        snippet=snippet[:1000],
                        url=link,
                        source=item.get("source", self._extract_domain(link)),
                        published_date=item.get("date"),
                    )
                )

            return SearchResponse(query=query, results=results, provider=self.name, success=True)

        except Exception as exc:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=str(exc),
            )

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain or "未知来源"
        except Exception:
            return "未知来源"


class BochaSearchProvider(BaseSearchProvider):
    """Bocha 搜索引擎。"""

    API_ENDPOINT = "https://api.bochaai.com/v1/web-search"

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys, "Bocha")

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "query": query,
            "summary": True,
            "count": max_results,
            "freshness": max(days, 1),
        }

        try:
            response = _post_with_retry(self.API_ENDPOINT, headers=headers, json=payload, timeout=10)
            if response.status_code != 200:
                error_msg = self._parse_error(response)
                logger.warning(f"[Bocha] 搜索失败: {error_msg}")
                return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

            try:
                data = response.json()
            except ValueError as exc:
                error_msg = f"响应JSON解析失败: {str(exc)}"
                logger.error(f"[Bocha] {error_msg}")
                return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

            if data.get("code") != 200:
                error_msg = data.get("msg") or f"API返回错误码: {data.get('code')}"
                return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

            logger.info(f"[Bocha] 搜索完成，query='{query}'")
            logger.debug(f"[Bocha] 原始响应: {data}")

            results = []
            value_list = data.get("data", {}).get("webPages", {}).get("value", [])
            for item in value_list[:max_results]:
                snippet = item.get("summary") or item.get("snippet", "")
                if snippet:
                    snippet = snippet[:500]
                results.append(
                    SearchResult(
                        title=item.get("name", ""),
                        snippet=snippet,
                        url=item.get("url", ""),
                        source=item.get("siteName") or self._extract_domain(item.get("url", "")),
                        published_date=item.get("datePublished"),
                    )
                )

            logger.info(f"[Bocha] 成功解析 {len(results)} 条结果")
            return SearchResponse(query=query, results=results, provider=self.name, success=True)

        except requests.exceptions.Timeout:
            error_msg = "请求超时"
            logger.error(f"[Bocha] {error_msg}")
            return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)
        except requests.exceptions.RequestException as exc:
            error_msg = f"网络请求失败: {str(exc)}"
            logger.error(f"[Bocha] {error_msg}")
            return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)
        except Exception as exc:
            error_msg = f"未知错误: {str(exc)}"
            logger.error(f"[Bocha] {error_msg}")
            return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

    @staticmethod
    def _parse_error(response) -> str:
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                error_data = response.json()
                return error_data.get("msg") or error_data.get("message") or str(error_data)
            return response.text[:200]
        except Exception:
            return f"HTTP {response.status_code}: {response.text[:200]}"

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain or "未知来源"
        except Exception:
            return "未知来源"


class BraveSearchProvider(BaseSearchProvider):
    """Brave Search 搜索引擎。"""

    API_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys, "Brave")

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        try:
            headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
            if days <= 1:
                freshness = "pd"
            elif days <= 7:
                freshness = "pw"
            elif days <= 30:
                freshness = "pm"
            else:
                freshness = "py"

            params = {
                "q": query,
                "count": min(max_results, 20),
                "freshness": freshness,
                "search_lang": "en",
                "country": "US",
                "safesearch": "moderate",
            }

            response = requests.get(self.API_ENDPOINT, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                error_msg = self._parse_error(response)
                logger.warning(f"[Brave] 搜索失败: {error_msg}")
                return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

            try:
                data = response.json()
            except ValueError as exc:
                error_msg = f"响应JSON解析失败: {str(exc)}"
                logger.error(f"[Brave] {error_msg}")
                return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

            logger.info(f"[Brave] 搜索完成，query='{query}'")
            logger.debug(f"[Brave] 原始响应: {data}")

            results = []
            web_results = data.get("web", {}).get("results", [])
            for item in web_results[:max_results]:
                published_date = None
                age = item.get("age") or item.get("page_age")
                if age:
                    try:
                        dt = datetime.fromisoformat(age.replace("Z", "+00:00"))
                        published_date = dt.strftime("%Y-%m-%d")
                    except (ValueError, AttributeError):
                        published_date = age

                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("description", "")[:500],
                        url=item.get("url", ""),
                        source=self._extract_domain(item.get("url", "")),
                        published_date=published_date,
                    )
                )

            logger.info(f"[Brave] 成功解析 {len(results)} 条结果")
            return SearchResponse(query=query, results=results, provider=self.name, success=True)

        except requests.exceptions.Timeout:
            error_msg = "请求超时"
            logger.error(f"[Brave] {error_msg}")
            return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)
        except requests.exceptions.RequestException as exc:
            error_msg = f"网络请求失败: {str(exc)}"
            logger.error(f"[Brave] {error_msg}")
            return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)
        except Exception as exc:
            error_msg = f"未知错误: {str(exc)}"
            logger.error(f"[Brave] {error_msg}")
            return SearchResponse(query=query, results=[], provider=self.name, success=False, error_message=error_msg)

    def _parse_error(self, response) -> str:
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                error_data = response.json()
                if "message" in error_data:
                    return error_data["message"]
                if "error" in error_data:
                    return error_data["error"]
                return str(error_data)
            return response.text[:200]
        except Exception:
            return f"HTTP {response.status_code}: {response.text[:200]}"

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain or "未知来源"
        except Exception:
            return "未知来源"
