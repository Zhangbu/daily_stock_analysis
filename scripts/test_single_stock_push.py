#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单股推送日志
"""
import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志输出
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

from src.config import get_config
from src.notification import NotificationService
from src.core.analysis_delivery import AnalysisDeliveryService
from src.analyzer import AnalysisResult

def test_notification_service():
    """测试通知服务"""
    print("\n" + "="*60)
    print("=== 测试通知服务 ===")
    print("="*60)

    # 获取配置
    config = get_config()
    print(f"\n配置加载成功:")
    print(f"  - SINGLE_STOCK_NOTIFY: {getattr(config, 'single_stock_notify', 'NOT_SET')}")
    print(f"  - TELEGRAM_BOT_TOKEN: {'已配置' if getattr(config, 'telegram_bot_token') else '未配置'}")
    print(f"  - TELEGRAM_CHAT_ID: {'已配置' if getattr(config, 'telegram_chat_id') else '未配置'}")
    print(f"  - EMAIL_SENDER: {'已配置' if getattr(config, 'email_sender') else '未配置'}")

    # 创建通知服务
    service = NotificationService()

    print(f"\n通知服务状态:")
    print(f"  - 可用渠道：{service.get_available_channels()}")
    print(f"  - 渠道名称：{service.get_channel_names()}")
    print(f"  - is_available: {service.is_available()}")
    print(f"  - 钉钉上下文：{service._has_context_channel()}")

    return service

def test_single_stock_report(service):
    """测试单股报告生成"""
    print("\n" + "="*60)
    print("=== 测试单股报告生成 ===")
    print("="*60)

    # 模拟分析结果
    result = AnalysisResult(
        code='000001',
        name='平安银行',
        sentiment_score=75,
        trend_prediction='看多',
        analysis_summary='技术面强势，资金流入明显',
        operation_advice='买入',
        dashboard={
            'core_conclusion': {
                'one_sentence': '建议逢低布局，预期目标价 15 元',
                'position_advice': {
                    'no_position': '建议建仓 30%',
                    'has_position': '继续持有，可加仓'
                }
            },
            'battle_plan': {
                'sniper_points': {
                    'ideal_buy': '12.50',
                    'secondary_buy': '12.20',
                    'stop_loss': '11.80',
                    'take_profit': '15.00'
                }
            }
        }
    )

    print(f"\n生成单股报告...")
    report = service.generate_single_stock_report(result)
    print(f"报告长度：{len(report)} 字符")
    print(f"\n报告预览 (前 500 字符):")
    print("-"*40)
    print(report[:500])
    print("...")
    print("-"*40)

    return report

def test_send_report(service, report):
    """测试发送报告"""
    print("\n" + "="*60)
    print("=== 测试发送报告 ===")
    print("="*60)

    print(f"\n开始推送...")
    result = service.send(report, email_stock_codes=['000001'])
    print(f"\n推送结果：{result}")

    return result

def test_delivery_service():
    """测试投送服务"""
    print("\n" + "="*60)
    print("=== 测试投送服务 ===")
    print("="*60)

    config = get_config()
    notifier = NotificationService()
    delivery = AnalysisDeliveryService(notifier=notifier, config=config)

    # 创建模拟结果
    result = AnalysisResult(
        code='000001',
        name='平安银行',
        sentiment_score=75,
        trend_prediction='看多',
        analysis_summary='技术面强势',
        operation_advice='买入'
    )

    from src.enums import ReportType

    print(f"\n测试 send_single_stock_report...")
    success = delivery.send_single_stock_report(
        code='000001',
        result=result,
        report_type=ReportType.SIMPLE
    )
    print(f"投送结果：{success}")

    return success

if __name__ == '__main__':
    print("\n" + "="*60)
    print("单股推送日志测试脚本")
    print("="*60)

    # 测试 1: 通知服务
    service = test_notification_service()

    if service.is_available():
        # 测试 2: 报告生成
        report = test_single_stock_report(service)

        # 测试 3: 发送报告
        test_send_report(service, report)

        # 测试 4: 投送服务
        test_delivery_service()
    else:
        print("\n⚠️  通知服务不可用，跳过发送测试")
        print("请检查 .env 文件中的通知渠道配置")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
