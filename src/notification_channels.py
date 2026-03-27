# -*- coding: utf-8 -*-
"""Notification channel metadata and detection helpers."""

from __future__ import annotations

from enum import Enum


class NotificationChannel(Enum):
    """通知渠道类型"""

    TELEGRAM = "telegram"
    EMAIL = "email"
    DISCORD = "discord"
    UNKNOWN = "unknown"


SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}


class ChannelDetector:
    """根据配置直接判断渠道类型（不再需要 URL 解析）。"""

    @staticmethod
    def get_channel_name(channel: NotificationChannel) -> str:
        names = {
            NotificationChannel.TELEGRAM: "Telegram",
            NotificationChannel.EMAIL: "邮件",
            NotificationChannel.DISCORD: "Discord机器人",
            NotificationChannel.UNKNOWN: "未知渠道",
        }
        return names.get(channel, "未知渠道")
