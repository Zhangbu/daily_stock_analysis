# -*- coding: utf-8 -*-
"""Tests for notification helper layers."""

import unittest
from types import SimpleNamespace

from src.notification_renderers import render_daily_report
from src.notification_transports import dispatch_notification_channel


class NotificationHelpersTestCase(unittest.TestCase):
    def test_render_daily_report_delegates_to_service_impl(self):
        service = SimpleNamespace(_generate_daily_report_impl=lambda results, report_date=None: "rendered")
        self.assertEqual(render_daily_report(service, []), "rendered")

    def test_dispatch_notification_channel_wechat_text(self):
        calls = []
        service = SimpleNamespace(
            NotificationChannel=SimpleNamespace(WECHAT="wechat", FEISHU="feishu", TELEGRAM="telegram", EMAIL="email",
                                               PUSHOVER="pushover", PUSHPLUS="pushplus", SERVERCHAN3="serverchan3",
                                               CUSTOM="custom", DISCORD="discord", ASTRBOT="astrbot"),
            _should_use_image_for_channel=lambda channel, image: False,
            send_to_wechat=lambda content: calls.append(content) or True,
            _stock_email_groups=[],
        )
        result = dispatch_notification_channel(
            service,
            channel="wechat",
            content="hello",
            image_bytes=None,
            email_stock_codes=None,
            email_send_to_all=False,
        )
        self.assertTrue(result)
        self.assertEqual(calls, ["hello"])


if __name__ == "__main__":
    unittest.main()
