# -*- coding: utf-8 -*-
"""Notification transport dispatch helpers."""

from __future__ import annotations

import logging
from typing import List, Optional

from src.notification_channels import NotificationChannel

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
    """Dispatch notification delivery for one channel (email/telegram/discord only)."""
    channel_value = channel.value if isinstance(channel, NotificationChannel) else str(channel)
    use_image = service._should_use_image_for_channel(channel, image_bytes)

    if channel_value == NotificationChannel.TELEGRAM.value:
        if use_image:
            return service._send_telegram_photo(image_bytes)
        return service.send_to_telegram(content)
    if channel_value == NotificationChannel.EMAIL.value:
        receivers = None
        if email_send_to_all and service._stock_email_groups:
            receivers = service.get_all_email_receivers()
        elif email_stock_codes and service._stock_email_groups:
            receivers = service.get_receivers_for_stocks(email_stock_codes)
        if use_image:
            return service._send_email_with_inline_image(image_bytes, receivers=receivers)
        return service.send_to_email(content, receivers=receivers)
    if channel_value == NotificationChannel.DISCORD.value:
        return service.send_to_discord(content)

    logger.warning(f"精简模式下不支持的通知渠道: {channel}")
    return False
