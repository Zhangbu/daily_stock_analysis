# -*- coding: utf-8 -*-
"""Integration tests for system configuration API endpoints."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config


class SystemConfigApiTestCase(unittest.TestCase):
    """System config API tests run with auth disabled (test config API in isolation)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519,000001",
                    "GEMINI_API_KEY=secret-key-value",
                    "SCHEDULE_TIME=18:00",
                    "LOG_LEVEL=INFO",
                    "ADMIN_AUTH_ENABLED=false",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        Config.reset_instance()

        auth._auth_enabled = None
        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=False)
        self.auth_patcher.start()

        app = create_app(static_dir=Path(self.temp_dir.name) / "empty-static")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        self.temp_dir.cleanup()

    def test_get_config_returns_raw_secret_value(self) -> None:
        response = self.client.get("/api/v1/system/config")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        item_map = {item["key"]: item for item in payload["items"]}
        self.assertEqual(item_map["GEMINI_API_KEY"]["value"], "secret-key-value")
        self.assertFalse(item_map["GEMINI_API_KEY"]["is_masked"])

    def test_put_config_updates_secret_and_plain_field(self) -> None:
        current = self.client.get("/api/v1/system/config").json()

        response = self.client.put(
            "/api/v1/system/config",
            json={
                "config_version": current["config_version"],
                "mask_token": "******",
                "reload_now": False,
                "items": [
                    {"key": "GEMINI_API_KEY", "value": "new-secret-value"},
                    {"key": "STOCK_LIST", "value": "600519,300750"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["applied_count"], 2)
        self.assertEqual(payload["skipped_masked_count"], 0)

        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("STOCK_LIST=600519,300750", env_content)
        self.assertIn("GEMINI_API_KEY=new-secret-value", env_content)

    def test_put_config_returns_conflict_when_version_is_stale(self) -> None:
        response = self.client.put(
            "/api/v1/system/config",
            json={
                "config_version": "stale-version",
                "items": [{"key": "STOCK_LIST", "value": "600519"}],
            },
        )
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error"], "config_version_conflict")

    def test_get_feature_flags_returns_api_toggles(self) -> None:
        response = self.client.get("/api/v1/system/features")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("agent_api", payload)
        self.assertIn("backtest_api", payload)
        self.assertIn("strategy_backtest_api", payload)
        self.assertIn("market_sync_api", payload)
        self.assertIn("screening_api", payload)

    def test_get_config_hides_deprecated_notification_keys(self) -> None:
        # Append deprecated keys into env file to verify API-level filtering.
        self.env_path.write_text(
            self.env_path.read_text(encoding="utf-8")
            + "WECHAT_WEBHOOK_URL=https://example.com/hook\n"
            + "PUSHPLUS_TOKEN=deprecated-token\n",
            encoding="utf-8",
        )
        Config.reset_instance()

        response = self.client.get("/api/v1/system/config")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        keys = {item["key"] for item in payload["items"]}
        self.assertNotIn("WECHAT_WEBHOOK_URL", keys)
        self.assertNotIn("PUSHPLUS_TOKEN", keys)

    def test_get_config_core_profile_returns_slimmed_keys(self) -> None:
        response = self.client.get("/api/v1/system/config?profile=core")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        keys = {item["key"] for item in payload["items"]}
        self.assertIn("STOCK_LIST", keys)
        self.assertIn("HK_STOCK_LIST", keys)
        self.assertIn("OPENAI_MODEL", keys)
        self.assertIn("GEMINI_API_KEYS", keys)
        self.assertIn("GEMINI_PER_MODEL_RPM", keys)
        self.assertIn("GEMINI_PER_MODEL_DAILY_LIMIT", keys)
        self.assertIn("LLM_RESPONSE_STYLE", keys)
        self.assertIn("EMAIL_SENDER", keys)
        self.assertIn("MARKET_SYNC_MARKETS", keys)
        self.assertIn("ENABLE_REALTIME_QUOTE", keys)
        self.assertNotIn("LOG_LEVEL", keys)

    def test_get_schema_core_profile_returns_slimmed_fields(self) -> None:
        response = self.client.get("/api/v1/system/config/schema?profile=core")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        keys = {
            field["key"]
            for category in payload["categories"]
            for field in category["fields"]
        }
        self.assertIn("STOCK_LIST", keys)
        self.assertIn("HK_STOCK_LIST", keys)
        self.assertIn("ENABLE_AGENT_API", keys)
        self.assertIn("LLM_RESPONSE_STYLE", keys)
        self.assertIn("GEMINI_PER_MODEL_RPM", keys)
        self.assertNotIn("LOG_LEVEL", keys)


if __name__ == "__main__":
    unittest.main()
