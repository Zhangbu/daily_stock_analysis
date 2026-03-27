# -*- coding: utf-8 -*-
"""Tests for notification helper layers."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from src.notification import NotificationService
from src.notification_renderers import render_daily_report
from src.notification_transports import dispatch_notification_channel


class NotificationHelpersTestCase(unittest.TestCase):
    def test_render_daily_report_delegates_to_service_impl(self):
        service = SimpleNamespace(_generate_daily_report_impl=lambda results, report_date=None: "rendered")
        self.assertEqual(render_daily_report(service, []), "rendered")

    def test_dispatch_notification_channel_telegram_text(self):
        calls = []
        service = SimpleNamespace(
            _should_use_image_for_channel=lambda channel, image: False,
            send_to_telegram=lambda content: calls.append(content) or True,
            _stock_email_groups=[],
        )
        result = dispatch_notification_channel(
            service,
            channel="telegram",
            content="hello",
            image_bytes=None,
            email_stock_codes=None,
            email_send_to_all=False,
        )
        self.assertTrue(result)
        self.assertEqual(calls, ["hello"])

    def test_telegram_request_kwargs_prefers_ca_bundle(self):
        service = NotificationService.__new__(NotificationService)
        service._telegram_config = {
            "verify_ssl": False,
            "ca_bundle": "/tmp/custom-ca.pem",
        }

        kwargs = service._telegram_request_kwargs(timeout=10)

        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(kwargs["verify"], "/tmp/custom-ca.pem")

    def test_send_telegram_message_stops_retry_on_cert_verify_error(self):
        service = NotificationService.__new__(NotificationService)
        service._telegram_config = {
            "verify_ssl": True,
            "ca_bundle": None,
        }

        with patch("src.notification.requests.post") as post_mock:
            post_mock.side_effect = requests.exceptions.SSLError(
                "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate"
            )

            ok = service._send_telegram_message(
                "https://api.telegram.org/bot123/sendMessage",
                "123456",
                "hello",
            )

        self.assertFalse(ok)
        self.assertEqual(post_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
