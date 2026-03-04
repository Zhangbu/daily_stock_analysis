# -*- coding: utf-8 -*-
"""
Tool Registry for the Agent framework.

Provides:
- ToolParameter / ToolDefinition dataclasses
- ToolRegistry: central tool registry with multi-provider schema generation
- TTL-based result caching for tool execution
- Async execution support
- @tool decorator for easy tool registration
"""

import asyncio
import hashlib
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ============================================================
# Cache configuration
# ============================================================

# Default TTL for tool result cache (5 minutes)
DEFAULT_CACHE_TTL: int = 300

# Tools that should NOT be cached (real-time data)
NON_CACHEABLE_TOOLS: set = {
    "get_realtime_quote",  # Real-time quotes change frequently
    "search_stock_news",   # News changes frequently
    "search_comprehensive_intel",  # Intelligence changes
}

# Tools with custom TTL (seconds)
CUSTOM_CACHE_TTL: Dict[str, int] = {
    "get_daily_history": 600,        # 10 minutes - historical data doesn't change often
    "get_chip_distribution": 300,    # 5 minutes
    "get_analysis_context": 300,     # 5 minutes
    "get_stock_info": 3600,          # 1 hour - fundamental info rarely changes
    "analyze_trend": 300,            # 5 minutes
    "get_market_indices": 60,        # 1 minute - market data changes fast
    "get_sector_rankings": 120,      # 2 minutes
}


# ============================================================
# Data classes
# ============================================================

@dataclass
class ToolParameter:
    """Schema for a single tool parameter."""
    name: str
    type: str  # "string" | "number" | "integer" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None


@dataclass
class ToolDefinition:
    """Complete definition of an agent-callable tool."""
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Callable
    category: str = "data"  # data | analysis | search | action

    # ----- Multi-provider schema converters -----

    def _params_json_schema(self) -> dict:
        """Convert parameters to JSON Schema (shared by OpenAI/Anthropic)."""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for p in self.parameters:
            prop: Dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required
        return schema

    def to_gemini_declaration(self) -> dict:
        """
        Convert to Gemini FunctionDeclaration dict (JSON Schema format).

        Uses lowercase JSON Schema types ("object", "string", etc.) as required
        by the google-genai SDK's ``parameters_json_schema`` field.
        """
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for p in self.parameters:
            prop: Dict[str, Any] = {
                "type": p.type,
                "description": p.description,
            }
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        decl: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
            },
        }
        if required:
            decl["parameters"]["required"] = required
        return decl

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI ``tools`` list element format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._params_json_schema(),
            },
        }

    def to_anthropic_tool(self) -> dict:
        """Convert to Anthropic ``tools`` list element format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._params_json_schema(),
        }


# ============================================================
# Tool Registry
# ============================================================

class ToolRegistry:
    """Central registry for all agent-callable tools.

    Features:
    - Tool registration and schema generation for multiple LLM providers
    - TTL-based result caching to avoid redundant tool calls
    - Async execution support for improved concurrency
    - Cache statistics for monitoring

    Usage::

        registry = ToolRegistry()
        registry.register(tool_def)
        result = registry.execute("get_realtime_quote", stock_code="600519")
        
        # With caching (automatic)
        result = registry.execute_with_cache("get_daily_history", stock_code="600519", days=60)
        
        # Async execution
        result = await registry.execute_async("get_realtime_quote", stock_code="600519")
    """

    def __init__(self, default_cache_ttl: int = DEFAULT_CACHE_TTL):
        self._tools: Dict[str, ToolDefinition] = {}
        # Cache: key -> (result, timestamp, hit_count)
        self._cache: Dict[str, Tuple[Any, float, int]] = {}
        self._default_cache_ttl = default_cache_ttl
        # Cache statistics
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    # ----- Registration -----

    def register(self, tool_def: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool_def.name in self._tools:
            logger.warning(f"Tool '{tool_def.name}' already registered, overwriting")
        self._tools[tool_def.name] = tool_def
        logger.debug(f"Registered tool: {tool_def.name} (category={tool_def.category})")

    def unregister(self, name: str) -> None:
        """Remove a registered tool."""
        self._tools.pop(name, None)

    # ----- Query -----

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Return a tool definition by name."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """List all tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def list_names(self) -> List[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    # ----- Cache Management -----

    def _make_cache_key(self, name: str, kwargs: Dict[str, Any]) -> str:
        """Generate a stable cache key from tool name and arguments."""
        # Sort kwargs for consistent keys
        sorted_args = json.dumps(kwargs, sort_keys=True, default=str)
        args_hash = hashlib.md5(sorted_args.encode()).hexdigest()[:8]
        return f"{name}:{args_hash}"

    def _get_cache_ttl(self, tool_name: str) -> int:
        """Get the appropriate TTL for a tool."""
        return CUSTOM_CACHE_TTL.get(tool_name, self._default_cache_ttl)

    def _is_cacheable(self, tool_name: str) -> bool:
        """Check if a tool's result should be cached."""
        return tool_name not in NON_CACHEABLE_TOOLS

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get a cached result if valid."""
        if cache_key not in self._cache:
            return None
        
        result, timestamp, hit_count = self._cache[cache_key]
        # Cache entry has expired (use 0 TTL check for tools that shouldn't be cached)
        return result

    def _set_cache(self, cache_key: str, result: Any, ttl: int) -> None:
        """Store a result in cache with TTL."""
        self._cache[cache_key] = (result, time.time(), 0)

    def _update_cache_hit(self, cache_key: str) -> None:
        """Increment hit count for a cached entry."""
        if cache_key in self._cache:
            result, timestamp, hit_count = self._cache[cache_key]
            self._cache[cache_key] = (result, timestamp, hit_count + 1)

    def clear_cache(self, tool_name: Optional[str] = None) -> int:
        """Clear cache entries, optionally filtered by tool name.
        
        Args:
            tool_name: If provided, only clear entries for this tool.
            
        Returns:
            Number of entries cleared.
        """
        if tool_name is None:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared all {count} cache entries")
            return count
        
        keys_to_remove = [k for k in self._cache if k.startswith(f"{tool_name}:")]
        for key in keys_to_remove:
            del self._cache[key]
        if keys_to_remove:
            logger.info(f"Cleared {len(keys_to_remove)} cache entries for tool '{tool_name}'")
        return len(keys_to_remove)

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries.
        
        Returns:
            Number of entries removed.
        """
        current_time = time.time()
        keys_to_remove = []
        
        for key, (result, timestamp, hit_count) in self._cache.items():
            tool_name = key.split(":")[0]
            ttl = self._get_cache_ttl(tool_name)
            if current_time - timestamp > ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._cache[key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} expired cache entries")
        return len(keys_to_remove)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0
        
        return {
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": f"{hit_rate:.1%}",
            "tools_registered": len(self._tools),
        }

    # ----- Multi-provider schema generation -----

    def to_gemini_declarations(self) -> List[dict]:
        """Generate Gemini FunctionDeclaration list."""
        return [t.to_gemini_declaration() for t in self._tools.values()]

    def to_openai_tools(self) -> List[dict]:
        """Generate OpenAI tools list."""
        return [t.to_openai_tool() for t in self._tools.values()]

    def to_anthropic_tools(self) -> List[dict]:
        """Generate Anthropic tools list."""
        return [t.to_anthropic_tool() for t in self._tools.values()]

    # ----- Execution -----

    def execute(self, name: str, **kwargs) -> Any:
        """Execute a registered tool by name (without caching).

        Returns the result as a JSON-serializable value.
        Raises ``KeyError`` if tool not found.
        Raises the handler's exception on execution failure.

        Supports Gemini namespaced tool names (e.g. default_api:get_realtime_quote -> get_realtime_quote).
        """
        tool_def = self._tools.get(name)
        if tool_def is None and ":" in name:
            # Gemini may return namespaced names like default_api:get_realtime_quote
            tool_def = self._tools.get(name.split(":", 1)[-1])
        if tool_def is None:
            raise KeyError(f"Tool '{name}' not found in registry. Available: {self.list_names()}")

        return tool_def.handler(**kwargs)

    def execute_with_cache(
        self, 
        name: str, 
        use_cache: bool = True,
        force_refresh: bool = False,
        **kwargs
    ) -> Tuple[Any, Dict[str, Any]]:
        """Execute a tool with TTL-based caching.

        Args:
            name: Tool name to execute.
            use_cache: Whether to use cache (default True).
            force_refresh: Force refresh cache even if valid entry exists.
            **kwargs: Tool arguments.

        Returns:
            Tuple of (result, metadata) where metadata contains cache info:
            - cached: bool - whether result was from cache
            - cache_key: str - the cache key used
            - ttl: int - TTL in seconds for this tool
            - execution_time: float - time taken to execute (0 if cached)
        """
        tool_def = self._tools.get(name)
        if tool_def is None and ":" in name:
            tool_def = self._tools.get(name.split(":", 1)[-1])
        if tool_def is None:
            raise KeyError(f"Tool '{name}' not found in registry. Available: {self.list_names()}")

        # Resolve actual tool name (strip namespace if present)
        actual_name = tool_def.name
        cache_key = self._make_cache_key(actual_name, kwargs)
        ttl = self._get_cache_ttl(actual_name)
        metadata = {"cache_key": cache_key, "ttl": ttl}

        # Check cache
        if use_cache and self._is_cacheable(actual_name) and not force_refresh:
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                # Check TTL expiration
                _, timestamp, _ = self._cache[cache_key]
                if time.time() - timestamp <= ttl:
                    self._cache_hits += 1
                    self._update_cache_hit(cache_key)
                    metadata["cached"] = True
                    metadata["execution_time"] = 0.0
                    logger.debug(f"Cache HIT for tool '{actual_name}' (key: {cache_key})")
                    return cached_result, metadata

        # Execute tool
        self._cache_misses += 1
        start_time = time.time()
        result = tool_def.handler(**kwargs)
        execution_time = time.time() - start_time

        # Store in cache if cacheable
        if use_cache and self._is_cacheable(actual_name):
            self._set_cache(cache_key, result, ttl)
            logger.debug(f"Cache MISS for tool '{actual_name}' (key: {cache_key}), cached for {ttl}s")

        metadata["cached"] = False
        metadata["execution_time"] = round(execution_time, 3)
        return result, metadata

    async def execute_async(self, name: str, **kwargs) -> Any:
        """Execute a tool asynchronously.

        This runs the tool handler in a thread pool to avoid blocking
        the event loop. Useful for I/O-bound tools.

        Args:
            name: Tool name to execute.
            **kwargs: Tool arguments.

        Returns:
            Tool execution result.
        """
        tool_def = self._tools.get(name)
        if tool_def is None and ":" in name:
            tool_def = self._tools.get(name.split(":", 1)[-1])
        if tool_def is None:
            raise KeyError(f"Tool '{name}' not found in registry. Available: {self.list_names()}")

        # Check if handler is already async
        if asyncio.iscoroutinefunction(tool_def.handler):
            return await tool_def.handler(**kwargs)
        
        # Run sync handler in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: tool_def.handler(**kwargs))

    async def execute_async_with_cache(
        self,
        name: str,
        use_cache: bool = True,
        force_refresh: bool = False,
        **kwargs
    ) -> Tuple[Any, Dict[str, Any]]:
        """Execute a tool asynchronously with caching.

        Combines async execution with TTL-based caching.

        Args:
            name: Tool name to execute.
            use_cache: Whether to use cache (default True).
            force_refresh: Force refresh cache even if valid entry exists.
            **kwargs: Tool arguments.

        Returns:
            Tuple of (result, metadata) same as execute_with_cache.
        """
        tool_def = self._tools.get(name)
        if tool_def is None and ":" in name:
            tool_def = self._tools.get(name.split(":", 1)[-1])
        if tool_def is None:
            raise KeyError(f"Tool '{name}' not found in registry. Available: {self.list_names()}")

        actual_name = tool_def.name
        cache_key = self._make_cache_key(actual_name, kwargs)
        ttl = self._get_cache_ttl(actual_name)
        metadata = {"cache_key": cache_key, "ttl": ttl}

        # Check cache
        if use_cache and self._is_cacheable(actual_name) and not force_refresh:
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                _, timestamp, _ = self._cache[cache_key]
                if time.time() - timestamp <= ttl:
                    self._cache_hits += 1
                    self._update_cache_hit(cache_key)
                    metadata["cached"] = True
                    metadata["execution_time"] = 0.0
                    logger.debug(f"Cache HIT for tool '{actual_name}' (async, key: {cache_key})")
                    return cached_result, metadata

        # Execute async
        self._cache_misses += 1
        start_time = time.time()
        result = await self.execute_async(actual_name, **kwargs)
        execution_time = time.time() - start_time

        # Store in cache
        if use_cache and self._is_cacheable(actual_name):
            self._set_cache(cache_key, result, ttl)
            logger.debug(f"Cache MISS for tool '{actual_name}' (async, key: {cache_key}), cached for {ttl}s")

        metadata["cached"] = False
        metadata["execution_time"] = round(execution_time, 3)
        return result, metadata


# ============================================================
# @tool decorator
# ============================================================

# Global default registry (singleton pattern)
_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Get or create the global default ToolRegistry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
    return _default_registry


def tool(
    name: str,
    description: str,
    category: str = "data",
    parameters: Optional[List[ToolParameter]] = None,
    registry: Optional[ToolRegistry] = None,
):
    """Decorator to register a function as an agent tool.

    Parameters can be specified explicitly or inferred from type hints.

    Example::

        @tool(name="get_realtime_quote", category="data",
              description="Get real-time stock quote")
        def get_realtime_quote(stock_code: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Infer parameters from type hints if not provided
        params = parameters
        if params is None:
            params = _infer_parameters(func)

        tool_def = ToolDefinition(
            name=name,
            description=description,
            parameters=params,
            handler=func,
            category=category,
        )

        target_registry = registry or get_default_registry()
        target_registry.register(tool_def)

        # Attach metadata to function for introspection
        func._tool_definition = tool_def
        return func

    return decorator


def _infer_parameters(func: Callable) -> List[ToolParameter]:
    """Infer ToolParameter list from function signature and type hints."""
    sig = inspect.signature(func)
    hints = getattr(func, '__annotations__', {})
    params: List[ToolParameter] = []

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        # Skip return annotation
        hint = hints.get(param_name, str)
        # Handle Optional and other typing constructs
        origin = getattr(hint, '__origin__', None)
        if origin is not None:
            # Optional[X] -> X, List[X] -> array, etc.
            args = getattr(hint, '__args__', ())
            if origin is list or (hasattr(origin, '__name__') and origin.__name__ == 'List'):
                param_type = "array"
            elif origin is dict:
                param_type = "object"
            else:
                # Union/Optional - use first non-None arg
                for a in args:
                    if a is not type(None):
                        param_type = type_map.get(a, "string")
                        break
                else:
                    param_type = "string"
        else:
            param_type = type_map.get(hint, "string")

        has_default = param.default is not inspect.Parameter.empty
        tp = ToolParameter(
            name=param_name,
            type=param_type,
            description=f"Parameter: {param_name}",
            required=not has_default,
            default=param.default if has_default else None,
        )
        params.append(tp)

    return params
