# -*- coding: utf-8 -*-
"""Tests for extracted analysis delivery service."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.core.analysis_delivery import AnalysisDeliveryService
from src.enums import ReportType
from src.notification_channels import NotificationChannel


class AnalysisDeliveryServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.notifier = Mock()
        self.notifier.is_available.return_value = True
        self.notifier.get_available_channels.return_value = [NotificationChannel.DISCORD]
        self.notifier.generate_dashboard_report.return_value = "dashboard"
        self.notifier.generate_single_stock_report.return_value = "single"
        self.notifier.save_report_to_file.return_value = "/tmp/report.md"
        self.notifier.send.return_value = True
        self.notifier.send_to_context.return_value = False
        self.notifier.send_to_discord.return_value = True
        self.service = AnalysisDeliveryService(notifier=self.notifier, config=SimpleNamespace(stock_email_groups=[]))
        self.result = SimpleNamespace(code="600519")

    def test_send_single_stock_report_uses_simple_renderer(self):
        sent = self.service.send_single_stock_report(
            code="600519",
            result=self.result,
            report_type=ReportType.SIMPLE,
        )

        self.assertTrue(sent)
        self.notifier.generate_single_stock_report.assert_called_once_with(self.result)
        self.notifier.send.assert_called_once_with("single", email_stock_codes=["600519"])

    def test_send_batch_notifications_sends_non_wechat_channels(self):
        self.service.send_batch_notifications([self.result], skip_push=False)

        self.notifier.generate_dashboard_report.assert_called()
        self.notifier.send_to_discord.assert_called_once_with("dashboard")

    def test_send_batch_notifications_skip_push_only_saves_report(self):
        self.service.send_batch_notifications([self.result], skip_push=True)

        self.notifier.save_report_to_file.assert_called_once()
        self.notifier.send_to_discord.assert_not_called()


if __name__ == "__main__":
    unittest.main()
