# -*- coding: utf-8 -*-
"""Delivery helpers extracted from the stock analysis pipeline."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from src.notification import NotificationChannel

logger = logging.getLogger(__name__)


class AnalysisDeliveryService:
    """Coordinate report rendering, persistence, and outbound notifications."""

    def __init__(self, *, notifier, config) -> None:
        self.notifier = notifier
        self.config = config

    def send_single_stock_report(self, *, code: str, result, report_type) -> bool:
        """Send a single-stock notification using the configured report format."""
        if not self.notifier.is_available():
            return False

        if report_type.value == "full":
            report_content = self.notifier.generate_dashboard_report([result])
            logger.info(f"[{code}] 使用完整报告格式")
        else:
            report_content = self.notifier.generate_single_stock_report(result)
            logger.info(f"[{code}] 使用精简报告格式")

        return self.notifier.send(report_content, email_stock_codes=[code])

    def send_batch_notifications(self, results: List, skip_push: bool = False) -> None:
        """Send or persist aggregated analysis notifications."""
        try:
            logger.info("生成决策仪表盘日报...")
            report = self.notifier.generate_dashboard_report(results)
            filepath = self.notifier.save_report_to_file(report)
            logger.info(f"决策仪表盘日报已保存: {filepath}")

            if skip_push:
                return

            if not self.notifier.is_available():
                logger.info("通知渠道未配置，跳过推送")
                return

            channels = self.notifier.get_available_channels()
            context_success = self.notifier.send_to_context(report)
            wechat_success = self._send_wechat_dashboard(results, channels)
            non_wechat_success = self._send_non_wechat_channels(results, report, channels)

            success = wechat_success or non_wechat_success or context_success
            if success:
                logger.info("决策仪表盘推送成功")
            else:
                logger.warning("决策仪表盘推送失败")
        except Exception as exc:
            logger.error(f"发送通知失败: {exc}")

    def _send_wechat_dashboard(self, results: List, channels: List[NotificationChannel]) -> bool:
        """Send the compact dashboard to WeChat if configured."""
        if NotificationChannel.WECHAT not in channels:
            return False

        dashboard_content = self.notifier.generate_wechat_dashboard(results)
        logger.info(f"企业微信仪表盘长度: {len(dashboard_content)} 字符")
        logger.debug(f"企业微信推送内容:\n{dashboard_content}")
        return self.notifier.send_to_wechat(dashboard_content)

    def _send_non_wechat_channels(
        self,
        results: List,
        report: str,
        channels: List[NotificationChannel],
    ) -> bool:
        """Send the full report to non-WeChat channels."""
        non_wechat_success = False
        stock_email_groups = getattr(self.config, "stock_email_groups", []) or []

        for channel in channels:
            if channel == NotificationChannel.WECHAT:
                continue
            if channel == NotificationChannel.FEISHU:
                non_wechat_success = self.notifier.send_to_feishu(report) or non_wechat_success
            elif channel == NotificationChannel.TELEGRAM:
                non_wechat_success = self.notifier.send_to_telegram(report) or non_wechat_success
            elif channel == NotificationChannel.EMAIL:
                non_wechat_success = self._send_email_groups(
                    results=results,
                    report=report,
                    stock_email_groups=stock_email_groups,
                ) or non_wechat_success
            elif channel == NotificationChannel.CUSTOM:
                non_wechat_success = self.notifier.send_to_custom(report) or non_wechat_success
            elif channel == NotificationChannel.PUSHPLUS:
                non_wechat_success = self.notifier.send_to_pushplus(report) or non_wechat_success
            elif channel == NotificationChannel.SERVERCHAN3:
                non_wechat_success = self.notifier.send_to_serverchan3(report) or non_wechat_success
            elif channel == NotificationChannel.DISCORD:
                non_wechat_success = self.notifier.send_to_discord(report) or non_wechat_success
            elif channel == NotificationChannel.PUSHOVER:
                non_wechat_success = self.notifier.send_to_pushover(report) or non_wechat_success
            elif channel == NotificationChannel.ASTRBOT:
                non_wechat_success = self.notifier.send_to_astrbot(report) or non_wechat_success
            else:
                logger.warning(f"未知通知渠道: {channel}")

        return non_wechat_success

    def _send_email_groups(
        self,
        *,
        results: List,
        report: str,
        stock_email_groups: List[Tuple[List[str], List[str]]],
    ) -> bool:
        """Send grouped email reports when per-stock recipients are configured."""
        if not stock_email_groups:
            return self.notifier.send_to_email(report)

        code_to_emails: Dict[str, Optional[List[str]]] = {}
        for result in results:
            if result.code in code_to_emails:
                continue
            emails = []
            for stocks, emails_list in stock_email_groups:
                if result.code in stocks:
                    emails.extend(emails_list)
            code_to_emails[result.code] = list(dict.fromkeys(emails)) if emails else None

        emails_to_results: Dict[Optional[Tuple], List] = defaultdict(list)
        for result in results:
            receivers = code_to_emails.get(result.code)
            emails_to_results[tuple(receivers) if receivers else None].append(result)

        success = False
        for key, group_results in emails_to_results.items():
            group_report = self.notifier.generate_dashboard_report(group_results)
            if key is None:
                success = self.notifier.send_to_email(group_report) or success
            else:
                success = self.notifier.send_to_email(group_report, receivers=list(key)) or success
        return success
