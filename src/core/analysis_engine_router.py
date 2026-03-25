# -*- coding: utf-8 -*-
"""Engine routing helpers extracted from the stock analysis pipeline."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class AnalysisEngineRouter:
    """Centralize standard-vs-agent analysis routing decisions."""

    def __init__(self, *, config) -> None:
        self.config = config

    def should_use_agent(self, *, code: str) -> bool:
        """Decide whether the agent analysis flow should be used."""
        use_agent = getattr(self.config, "agent_mode", False)
        if use_agent:
            return True

        configured_skills = getattr(self.config, "agent_skills", [])
        if configured_skills and configured_skills != ["all"]:
            logger.info(f"[{code}] Auto-enabled agent mode due to configured skills: {configured_skills}")
            return True
        return False

    def route(
        self,
        *,
        code: str,
        run_agent: Callable[[], object],
        run_standard: Callable[[], object],
    ):
        """Execute the selected analysis engine."""
        if self.should_use_agent(code=code):
            logger.info(f"[{code}] 启用 Agent 模式进行分析")
            return run_agent()
        return run_standard()
