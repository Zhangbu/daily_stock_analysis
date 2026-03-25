# -*- coding: utf-8 -*-
"""Tests for extracted analysis engine router."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.core.analysis_engine_router import AnalysisEngineRouter


class AnalysisEngineRouterTestCase(unittest.TestCase):
    def test_should_use_agent_when_explicitly_enabled(self):
        router = AnalysisEngineRouter(config=SimpleNamespace(agent_mode=True, agent_skills=[]))

        self.assertTrue(router.should_use_agent(code="600519"))

    def test_should_use_agent_when_specific_skills_configured(self):
        router = AnalysisEngineRouter(config=SimpleNamespace(agent_mode=False, agent_skills=["news"]))

        self.assertTrue(router.should_use_agent(code="600519"))

    def test_route_prefers_standard_when_agent_not_enabled(self):
        router = AnalysisEngineRouter(config=SimpleNamespace(agent_mode=False, agent_skills=["all"]))
        run_agent = Mock(return_value="agent")
        run_standard = Mock(return_value="standard")

        result = router.route(code="600519", run_agent=run_agent, run_standard=run_standard)

        self.assertEqual(result, "standard")
        run_agent.assert_not_called()
        run_standard.assert_called_once()


if __name__ == "__main__":
    unittest.main()
