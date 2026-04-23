# -*- coding: utf-8 -*-
"""
Runtime loaders for profile and strategy YAML definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = PROJECT_ROOT / "profiles"
STRATEGIES_DIR = PROJECT_ROOT / "strategies"


@dataclass
class ProfileDefinition:
    name: str
    display_name: str
    description: str
    stock_universe: List[str] = field(default_factory=list)
    data_source: str = "yfinance"
    interval: str = "1d"
    lookback_days: int = 250
    default_strategy: str = ""


@dataclass
class StrategyDefinition:
    name: str
    display_name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Definition file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML payload in {path}")

    return payload


def _normalize_code_list(items: List[Any]) -> List[str]:
    normalized: List[str] = []
    for item in items:
        if item is None:
            continue
        value = str(item).strip().upper()
        if value:
            normalized.append(value)
    return normalized


def load_profile_definition(profile_name: str) -> ProfileDefinition:
    payload = _load_yaml(PROFILES_DIR / f"{profile_name}.yaml")
    data = payload.get("data") or {}
    strategy = payload.get("strategy") or {}

    return ProfileDefinition(
        name=str(payload.get("name") or profile_name).strip(),
        display_name=str(payload.get("display_name") or profile_name).strip(),
        description=str(payload.get("description") or "").strip(),
        stock_universe=_normalize_code_list(payload.get("stock_universe") or []),
        data_source=str(data.get("source") or "yfinance").strip().lower(),
        interval=str(data.get("interval") or "1d").strip(),
        lookback_days=int(data.get("lookback_days") or 250),
        default_strategy=str(strategy.get("default") or "").strip(),
    )


def load_strategy_definition(strategy_name: str) -> StrategyDefinition:
    payload = _load_yaml(STRATEGIES_DIR / f"{strategy_name}.yaml")

    return StrategyDefinition(
        name=str(payload.get("name") or strategy_name).strip(),
        display_name=str(payload.get("display_name") or strategy_name).strip(),
        description=str(payload.get("description") or "").strip(),
        parameters=dict(payload.get("parameters") or {}),
    )
