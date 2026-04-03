#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股分析推送日志测试 - 模拟完整的个股分析流程
"""
import os
import sys
import logging
import time

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

logger = logging.getLogger(__name__)

def test_submit_analysis():
    """测试提交个股分析任务"""
    from src.services.task_service import TaskService
    from src.enums import ReportType

    task_service = TaskService.get_instance()

    print("\n" + "="*60)
    print("=== 测试提交个股分析任务 ===")
    print("="*60)

    # 提交分析任务（异步）
    result = task_service.submit_analysis(
        code='000001',
        report_type=ReportType.SIMPLE,
        query_source='test'
    )

    print(f"\n任务提交结果：{result}")

    # 等待一段时间让任务执行
    print("\n等待任务执行 (10 秒)...")
    time.sleep(10)

    # 检查任务状态
    task_status = task_service.get_task_status(result['task_id'])
    print(f"\n任务状态：{task_status}")

    return result['task_id']

if __name__ == '__main__':
    print("\n" + "="*60)
    print("个股分析推送日志测试 - 完整版")
    print("="*60)

    try:
        test_submit_analysis()
    except Exception as e:
        logger.exception(f"测试失败：{e}")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
