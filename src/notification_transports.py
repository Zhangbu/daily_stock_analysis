# -*- coding: utf-8 -*-
"""Notification transport dispatch helpers."""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def dispatch_notification_channel(
    service,
    *,
    channel,
    content: str,
    image_bytes: Optional[bytes],
    email_stock_codes: Optional[List[str]],
    email_send_to_all: bool,
) -> bool:
    """Dispatch notification delivery for one channel."""
    use_image = service._should_use_image_for_channel(channel, image_bytes)

    if channel == service.NotificationChannel.WECHAT:
        if use_image:
            return service._send_wechat_image(image_bytes)
        return service.send_to_wechat(content)
    if channel == service.NotificationChannel.FEISHU:
        return service.send_to_feishu(content)
    if channel == service.NotificationChannel.TELEGRAM:
        if use_image:
            return service._send_telegram_photo(image_bytes)
        return service.send_to_telegram(content)
    if channel == service.NotificationChannel.EMAIL:
        receivers = None
        if email_send_to_all and service._stock_email_groups:
            receivers = service.get_all_email_receivers()
        elif email_stock_codes and service._stock_email_groups:
            receivers = service.get_receivers_for_stocks(email_stock_codes)
        if use_image:
            return service._send_email_with_inline_image(image_bytes, receivers=receivers)
        return service.send_to_email(content, receivers=receivers)
    if channel == service.NotificationChannel.PUSHOVER:
        return service.send_to_pushover(content)
    if channel == service.NotificationChannel.PUSHPLUS:
        return service.send_to_pushplus(content)
    if channel == service.NotificationChannel.SERVERCHAN3:
        return service.send_to_serverchan3(content)
    if channel == service.NotificationChannel.CUSTOM:
        if use_image:
            return service._send_custom_webhook_image(image_bytes, fallback_content=content)
        return service.send_to_custom(content)
    if channel == service.NotificationChannel.DISCORD:
        return service.send_to_discord(content)
    if channel == service.NotificationChannel.ASTRBOT:
        return service.send_to_astrbot(content)

    logger.warning(f"不支持的通知渠道: {channel}")
    return False
