# -*- coding: utf-8 -*-
"""Delivery helpers extracted from the stock analysis pipeline."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from src.notification_channels import NotificationChannel

logger = logging.getLogger(__name__)


class AnalysisDeliveryService:
    """Coordinate report rendering, persistence, and outbound notifications."""

    def __init__(self, *, notifier, config) -> None:
        self.notifier = notifier
        self.config = config

    def send_single_stock_report(self, *, code: str, result, report_type) -> bool:
        """Send a single-stock notification using the configured report format."""
        import traceback
        
        logger.info(f"[{code}] 开始发送单股报告，报告类型：{report_type}")
        logger.info(f"[{code}] 通知服务可用性：{self.notifier.is_available()}")
        logger.info(f"[{code}] 可用的通知渠道：{self.notifier.get_available_channels()}")
        logger.info(f"[{code}] dashboard 类型：{type(result.dashboard).__name__ if hasattr(result, 'dashboard') else 'N/A'}")

        if not self.notifier.is_available():
            logger.warning(f"[{code}] 通知服务不可用，跳过推送")
            return False

        try:
            if report_type.value == "full":
                report_content = self.notifier.generate_dashboard_report([result])
                logger.info(f"[{code}] 使用完整报告格式，报告长度：{len(report_content)} 字符")
            else:
                report_content = self.notifier.generate_single_stock_report(result)
                logger.info(f"[{code}] 使用精简报告格式，报告长度：{len(report_content)} 字符")
        except Exception as e:
            logger.exception(f"[{code}] 生成报告失败：{e}")
            logger.error(f"[{code}] 堆栈跟踪：{traceback.format_exc()}")
            return False

        logger.info(f"[{code}] 开始推送到通知渠道...")
        result = self.notifier.send(report_content, email_stock_codes=[code])
        logger.info(f"[{code}] 推送结果：{result}")
        return result

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

            context_success = self.notifier.send_to_context(report)
            channel_success = self._send_available_channels(
                results=results,
                report=report,
                channels=self.notifier.get_available_channels(),
            )

            success = channel_success or context_success
            if success:
                logger.info("决策仪表盘推送成功")
            else:
                logger.warning("决策仪表盘推送失败")
        except Exception as exc:
            logger.error(f"发送通知失败: {exc}")

    def _send_available_channels(
        self,
        results: List,
        report: str,
        channels: List[NotificationChannel],
    ) -> bool:
        """Send the full report to available channels (telegram/email/discord)."""
        channel_success = False
        stock_email_groups = getattr(self.config, "stock_email_groups", []) or []

        for channel in channels:
            if channel == NotificationChannel.TELEGRAM:
                channel_success = self.notifier.send_to_telegram(report) or channel_success
            elif channel == NotificationChannel.EMAIL:
                channel_success = self._send_email_groups(
                    results=results,
                    report=report,
                    stock_email_groups=stock_email_groups,
                ) or channel_success
            elif channel == NotificationChannel.DISCORD:
                channel_success = self.notifier.send_to_discord(report) or channel_success
            else:
                logger.warning(f"精简模式下忽略通知渠道: {channel}")

        return channel_success

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
