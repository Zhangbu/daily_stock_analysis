# -*- coding: utf-8 -*-
"""
===================================
分析相关模型
===================================

职责：
1. 定义分析请求和响应模型
2. 定义任务状态模型
3. 定义异步任务队列相关模型
"""

from typing import Optional, List, Any, Dict
from enum import Enum

from pydantic import BaseModel, Field
from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN


class TaskStatusEnum(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    """Analysis request parameters"""
    
    stock_code: Optional[str] = Field(
        None, 
        description="单只股票代码", 
        example="600519"
    )
    stock_codes: Optional[List[str]] = Field(
        None, 
        description="多只股票代码（与 stock_code 二选一）",
        example=["600519", "000858"]
    )
    report_type: str = Field(
        "detailed",
        description="报告类型：simple(精简) / detailed(完整) / full(完整) / brief(简洁)",
        pattern="^(simple|detailed|full|brief)$",
    )
    force_refresh: bool = Field(
        False,
        description="是否强制刷新（忽略缓存）"
    )
    async_mode: bool = Field(
        False,
        description="是否使用异步模式"
    )
    stock_name: Optional[str] = Field(
        None,
        description="用户选中的股票名称（自动补全时提供）",
        example="贵州茅台"
    )
    original_query: Optional[str] = Field(
        None,
        description="用户原始输入（如茅台、gzmt、600519）",
        example="茅台"
    )
    selection_source: Optional[str] = Field(
        None,
        description="股票选择来源：manual(手动输入) | autocomplete(自动补全) | import(导入) | image(图片识别)",
        pattern=SELECTION_SOURCE_PATTERN,
        example="autocomplete"
    )
    notify: bool = Field(
        True,
        description="是否发送推送通知（Telegram/企业微信等）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "600519",
                "report_type": "detailed",
                "force_refresh": False,
                "async_mode": False,
                "stock_name": "贵州茅台",
                "original_query": "茅台",
                "selection_source": "autocomplete",
                "notify": True
            }
        }


class AnalysisResultResponse(BaseModel):
    """分析结果响应模型"""
    
    query_id: str = Field(..., description="分析记录唯一标识")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    report: Optional[Any] = Field(None, description="分析报告")
    created_at: str = Field(..., description="创建时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "abc123def456",
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "report": {
                    "summary": {
                        "sentiment_score": 75,
                        "operation_advice": "持有"
                    }
                },
                "created_at": "2024-01-01T12:00:00"
            }
        }


class Mag7StrategyOption(BaseModel):
    """Available Mag7 strategy option."""

    name: str = Field(..., description="策略内部标识")
    display_name: str = Field(..., description="策略显示名称")
    description: str = Field(..., description="策略描述")


class ProfileStockItemResponse(BaseModel):
    """Per-stock metadata returned by a strategy profile."""

    code: str = Field(..., description="股票代码")
    name_en: str = Field(..., description="英文名")
    name_zh: str = Field(..., description="中文名")
    sector: str = Field(..., description="板块/行业大类")
    industry: Optional[str] = Field(None, description="细分行业")


class Mag7ProfileMetaResponse(BaseModel):
    """Mag7 profile metadata for the dedicated UI."""

    profile_name: str = Field(..., description="画像名称")
    display_name: str = Field(..., description="画像显示名称")
    description: str = Field(..., description="画像描述")
    default_strategy: str = Field(..., description="默认策略")
    stock_universe: List[str] = Field(default_factory=list, description="默认股票池")
    stock_items: List[ProfileStockItemResponse] = Field(default_factory=list, description="股票元数据")
    strategies: List[Mag7StrategyOption] = Field(default_factory=list, description="可用策略列表")


class Mag7RunRequest(BaseModel):
    """Dedicated request model for running Mag7 strategies."""

    strategy_name: str = Field(..., description="策略名称", example="mag7_ma_pullback")
    stock_codes: Optional[List[str]] = Field(
        None,
        description="可选：覆盖默认股票池，仅分析选择的股票",
        example=["AAPL", "NVDA", "MSFT"],
    )


class Mag7SignalResponse(BaseModel):
    """Executable strategy signal summary."""

    strategy_name: str = Field(..., description="策略名称")
    score: int = Field(..., description="评分", ge=0, le=100)
    grade: str = Field(..., description="评级，例如 A/B/C/D")
    passed: bool = Field(..., description="是否通过策略阈值")
    verdict: str = Field(..., description="结论")
    entry_zone: str = Field(..., description="参考介入区")
    stop_loss: str = Field(..., description="参考止损位")
    target_hint: str = Field(..., description="参考目标提示")
    reasons: List[str] = Field(default_factory=list, description="理由")
    risks: List[str] = Field(default_factory=list, description="风险")
    metrics: Dict[str, float] = Field(default_factory=dict, description="指标快照")


class Mag7TrendSnapshot(BaseModel):
    """Trend snapshot used by the Mag7 UI."""

    trend_status: str = Field(..., description="趋势状态")
    buy_signal: str = Field(..., description="技术分析买卖信号")
    ma5: float = Field(..., description="MA5")
    ma10: float = Field(..., description="MA10")
    ma20: float = Field(..., description="MA20")
    ma60: float = Field(..., description="MA60")
    bias_ma5: float = Field(..., description="相对 MA5 乖离率")
    volume_ratio_5d: float = Field(..., description="5 日量能比")


class Mag7ResultItem(BaseModel):
    """Per-stock result in the dedicated Mag7 run response."""

    code: str = Field(..., description="股票代码")
    profile_name: str = Field(..., description="画像名称")
    strategy_name: str = Field(..., description="策略名称")
    trend: Mag7TrendSnapshot = Field(..., description="趋势快照")
    signal: Mag7SignalResponse = Field(..., description="策略结果")


class Mag7RunResponse(BaseModel):
    """Dedicated synchronous Mag7 run response."""

    profile_name: str = Field(..., description="画像名称")
    strategy_name: str = Field(..., description="策略名称")
    stock_codes: List[str] = Field(default_factory=list, description="本次分析股票池")
    results: List[Mag7ResultItem] = Field(default_factory=list, description="分析结果")


class TaskAccepted(BaseModel):
    """异步任务接受响应"""
    
    task_id: str = Field(..., description="任务 ID，用于查询状态")
    status: str = Field(
        ..., 
        description="任务状态",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="提示信息")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "pending",
                "message": "Analysis task accepted"
            }
        }


class BatchTaskAcceptedItem(BaseModel):
    """批量异步任务中的单个成功提交项。"""

    task_id: str = Field(..., description="任务 ID，用于查询状态")
    stock_code: str = Field(..., description="股票代码")
    status: str = Field(
        ...,
        description="任务状态",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="提示信息")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "stock_code": "600519",
                "status": "pending",
                "message": "分析任务已加入队列: 600519"
            }
        }


class BatchDuplicateTaskItem(BaseModel):
    """批量异步任务中的重复提交项。"""

    stock_code: str = Field(..., description="股票代码")
    existing_task_id: str = Field(..., description="已存在的任务 ID")
    message: str = Field(..., description="错误信息")

    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "600519",
                "existing_task_id": "task_existing_123",
                "message": "股票 600519 正在分析中 (task_id: task_existing_123)"
            }
        }


class BatchTaskAcceptedResponse(BaseModel):
    """批量异步任务接受响应。"""

    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="成功提交的任务列表")
    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="重复而跳过的任务列表")
    message: str = Field(..., description="汇总信息")

    class Config:
        json_schema_extra = {
            "example": {
                "accepted": [
                    {
                        "task_id": "task_abc123",
                        "stock_code": "600519",
                        "status": "pending",
                        "message": "分析任务已加入队列: 600519"
                    }
                ],
                "duplicates": [
                    {
                        "stock_code": "000858",
                        "existing_task_id": "task_existing_456",
                        "message": "股票 000858 正在分析中 (task_id: task_existing_456)"
                    }
                ],
                "message": "已提交 1 个任务，1 个重复跳过"
            }
        }


class TaskStatus(BaseModel):
    """Task status model"""
    
    task_id: str = Field(..., description="任务 ID")
    status: str = Field(
        ..., 
        description="任务状态",
        pattern="^(pending|processing|completed|failed)$"
    )
    progress: Optional[int] = Field(
        None, 
        description="进度百分比 (0-100)",
        ge=0,
        le=100
    )
    result: Optional[AnalysisResultResponse] = Field(
        None, 
        description="分析结果（仅在 completed 时存在）"
    )
    error: Optional[str] = Field(
        None, 
        description="错误信息（仅在 failed 时存在）"
    )
    stock_name: Optional[str] = Field(None, description="股票名称")
    original_query: Optional[str] = Field(None, description="用户原始输入")
    selection_source: Optional[str] = Field(
        None,
        description="选择来源",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "completed",
                "progress": 100,
                "result": None,
                "error": None,
                "stock_name": "贵州茅台",
                "original_query": "茅台",
                "selection_source": "autocomplete"
            }
        }


class TaskInfo(BaseModel):
    """
    Task details model

    Used for task list and SSE event delivery
    """
    
    task_id: str = Field(..., description="任务 ID")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    status: TaskStatusEnum = Field(..., description="任务状态")
    progress: int = Field(0, description="进度百分比 (0-100)", ge=0, le=100)
    message: Optional[str] = Field(None, description="状态消息")
    report_type: str = Field("detailed", description="报告类型")
    created_at: str = Field(..., description="创建时间")
    started_at: Optional[str] = Field(None, description="开始执行时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    error: Optional[str] = Field(None, description="错误信息（仅在 failed 时存在）")
    original_query: Optional[str] = Field(None, description="用户原始输入")
    selection_source: Optional[str] = Field(
        None,
        description="选择来源",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123def456",
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "status": "processing",
                "progress": 50,
                "message": "正在分析中...",
                "report_type": "detailed",
                "created_at": "2026-02-05T10:30:00",
                "started_at": "2026-02-05T10:30:01",
                "completed_at": None,
                "error": None,
                "original_query": "茅台",
                "selection_source": "autocomplete"
            }
        }


class TaskListResponse(BaseModel):
    """任务列表响应模型"""
    
    total: int = Field(..., description="任务总数")
    pending: int = Field(..., description="等待中的任务数")
    processing: int = Field(..., description="处理中的任务数")
    tasks: List[TaskInfo] = Field(..., description="任务列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 3,
                "pending": 1,
                "processing": 2,
                "tasks": []
            }
        }


class DuplicateTaskErrorResponse(BaseModel):
    """重复任务错误响应模型"""
    
    error: str = Field("duplicate_task", description="错误类型")
    message: str = Field(..., description="错误信息")
    stock_code: str = Field(..., description="股票代码")
    existing_task_id: str = Field(..., description="已存在的任务 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "duplicate_task",
                "message": "股票 600519 正在分析中",
                "stock_code": "600519",
                "existing_task_id": "abc123def456"
            }
        }
