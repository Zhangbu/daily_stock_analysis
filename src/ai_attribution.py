# -*- coding: utf-8 -*-
"""
===================================
AI 归因分析模块 - 分析股价变动原因
===================================

核心功能：
1. 新闻事件分类（业绩公告、减持/增持、监管处罚、行业政策、市场情绪等）
2. 时间轴关联（将新闻事件与股价变动时间点关联）
3. 归因分析引擎（结合当日涨跌幅和新闻类型，生成归因结论）

目标：让 AI 不仅说"趋势弱"，还要分析出"是因为业绩雷、减持公告，还是跟随大盘无理性的回撤"
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class NewsEventType(Enum):
    """新闻事件类型枚举"""
    EARNINGS_POSITIVE = "业绩利好"        # 业绩预增、扭亏为盈
    EARNINGS_NEGATIVE = "业绩利空"        # 业绩预亏、大幅下滑
    INSIDER_SELLING = "减持"              # 股东/高管减持
    INSIDER_BUYING = "增持"               # 股东/高管增持
    REGULATORY = "监管处罚"               # 立案调查、处罚
    POLICY_POSITIVE = "政策利好"          # 行业政策支持
    POLICY_NEGATIVE = "政策利空"          # 行业政策限制
    CONTRACT = "合同/订单"                # 中标、大合同
    DIVIDEND = "分红"                     # 分红派息
    LISTING = "上市/退市"                 # IPO、退市相关
    MERGER = "并购重组"                   # 收购、重组
    MARKET_SENTIMENT = "市场情绪"         # 大盘整体情绪
    SECTOR_ROTATION = "板块轮动"          # 行业资金流动
    UNKNOWN = "未知"                      # 未分类


class AttributionCause(Enum):
    """归因原因枚举"""
    EARNINGS_MISS = "业绩不及预期"        # 业绩雷
    INSIDER_SELLING = "减持压力"          # 减持公告
    REGULATORY_RISK = "监管风险"          # 处罚/调查
    POLICY_HEADWIND = "政策利空"          # 政策限制
    MARKET_CORRECTION = "大盘回调"        # 跟随大盘
    SECTOR_ROTATION = "板块轮动"          # 行业资金流出
    TECHNICAL_BREAKDOWN = "技术破位"      # 跌破支撑
    PROFIT_TAKING = "获利回吐"            # 涨多回调
    UNKNOWN = "无明显原因"                # 无明确原因


@dataclass
class NewsEvent:
    """新闻事件数据类"""
    title: str                           # 新闻标题
    snippet: str                         # 新闻摘要
    source: str                          # 来源
    published_date: Optional[str] = None # 发布日期
    event_type: NewsEventType = NewsEventType.UNKNOWN  # 事件类型
    sentiment: float = 0.0               # 情绪值 (-1 到 1)
    relevance: float = 0.5               # 相关性 (0 到 1)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'snippet': self.snippet,
            'source': self.source,
            'published_date': self.published_date,
            'event_type': self.event_type.value,
            'sentiment': self.sentiment,
            'relevance': self.relevance,
        }


@dataclass
class AttributionResult:
    """归因分析结果"""
    stock_code: str
    stock_name: str
    
    # 价格变动
    price_change_pct: float = 0.0        # 涨跌幅
    price_direction: str = "neutral"     # up/down/neutral
    
    # 主因分析
    primary_cause: AttributionCause = AttributionCause.UNKNOWN
    primary_cause_confidence: float = 0.0
    primary_cause_description: str = ""
    
    # 次要因素
    secondary_causes: List[AttributionCause] = field(default_factory=list)
    secondary_cause_descriptions: List[str] = field(default_factory=list)
    
    # 关联新闻
    related_news: List[NewsEvent] = field(default_factory=list)
    
    # 板块对比
    sector_name: str = ""
    sector_change_pct: float = 0.0
    relative_strength: str = "neutral"   # outperform/underperform/neutral
    
    # 归因描述
    attribution_summary: str = ""
    action_suggestion: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'price_change_pct': self.price_change_pct,
            'price_direction': self.price_direction,
            'primary_cause': self.primary_cause.value,
            'primary_cause_confidence': self.primary_cause_confidence,
            'primary_cause_description': self.primary_cause_description,
            'secondary_causes': [c.value for c in self.secondary_causes],
            'secondary_cause_descriptions': self.secondary_cause_descriptions,
            'related_news': [n.to_dict() for n in self.related_news],
            'sector_name': self.sector_name,
            'sector_change_pct': self.sector_change_pct,
            'relative_strength': self.relative_strength,
            'attribution_summary': self.attribution_summary,
            'action_suggestion': self.action_suggestion,
        }


class NewsEventClassifier:
    """
    新闻事件分类器
    
    使用关键词匹配对新闻进行分类
    """
    
    # 分类关键词映射
    CLASSIFICATION_KEYWORDS = {
        NewsEventType.EARNINGS_POSITIVE: [
            '业绩预增', '业绩大幅增长', '扭亏为盈', '净利增长', '利润大增',
            '业绩超预期', '业绩报喜', '业绩亮眼', '营收增长', '净利润增长',
            'earnings beat', 'profit surge', 'revenue growth'
        ],
        NewsEventType.EARNINGS_NEGATIVE: [
            '业绩预亏', '业绩大幅下滑', '亏损', '业绩爆雷', '业绩不及预期',
            '净利下降', '利润下滑', '业绩变脸', '业绩亏损', '首亏',
            'earnings miss', 'loss', 'profit decline'
        ],
        NewsEventType.INSIDER_SELLING: [
            '减持', '股东减持', '高管减持', '大股东减持', '减持计划',
            '减持股份', '拟减持', '减持公告', 'insider selling', 'share sale'
        ],
        NewsEventType.INSIDER_BUYING: [
            '增持', '股东增持', '高管增持', '大股东增持', '增持计划',
            '增持股份', '拟增持', '增持公告', 'insider buying', 'share purchase'
        ],
        NewsEventType.REGULATORY: [
            '立案调查', '处罚', '行政处罚', '监管函', '警示函',
            '证监会', '交易所问询', '违规', '造假', '财务造假',
            'investigation', 'penalty', 'regulatory'
        ],
        NewsEventType.POLICY_POSITIVE: [
            '政策支持', '政策利好', '国家政策', '行业扶持', '补贴',
            '纳入医保', '采购目录', '政策红利', 'industry support', 'policy benefit'
        ],
        NewsEventType.POLICY_NEGATIVE: [
            '政策限制', '政策利空', '监管收紧', '行业整顿', '限价',
            '集采', '带量采购', '反垄断', '政策风险', 'policy restriction'
        ],
        NewsEventType.CONTRACT: [
            '中标', '签订合同', '大订单', '重大合同', '订单',
            '中标公告', '合同签署', 'win contract', 'new order'
        ],
        NewsEventType.DIVIDEND: [
            '分红', '派息', '送股', '转增', '分红方案',
            '现金分红', '股息', 'dividend', 'payout'
        ],
        NewsEventType.MERGER: [
            '并购', '重组', '收购', '合并', '借壳',
            '资产重组', '并购重组', 'merger', 'acquisition', 'M&A'
        ],
        NewsEventType.MARKET_SENTIMENT: [
            '大盘', '指数', 'A股', '市场情绪', '恐慌',
            '整体市场', '系统性', 'market sentiment', 'market crash'
        ],
        NewsEventType.SECTOR_ROTATION: [
            '板块', '行业', '概念', '题材', '资金流入', '资金流出',
            '板块轮动', '行业龙头', 'sector rotation', 'industry flow'
        ],
    }
    
    # 情绪关键词
    POSITIVE_KEYWORDS = [
        '利好', '增长', '上涨', '突破', '创新高', '超预期',
        'positive', 'surge', 'rally', 'breakthrough', 'beat'
    ]
    NEGATIVE_KEYWORDS = [
        '利空', '下降', '下跌', '跌破', '创新低', '不及预期',
        'negative', 'drop', 'fall', 'breakdown', 'miss'
    ]
    
    def classify(self, title: str, snippet: str = "") -> Tuple[NewsEventType, float]:
        """
        对新闻进行分类
        
        Args:
            title: 新闻标题
            snippet: 新闻摘要
            
        Returns:
            (事件类型, 情绪值)
        """
        text = f"{title} {snippet}".lower()
        
        # 统计各类型的匹配分数
        scores = {}
        for event_type, keywords in self.CLASSIFICATION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > 0:
                scores[event_type] = score
        
        # 选择得分最高的类型
        if scores:
            best_type = max(scores, key=scores.get)
        else:
            best_type = NewsEventType.UNKNOWN
        
        # 计算情绪值
        positive_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw.lower() in text)
        negative_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw.lower() in text)
        
        if positive_count > negative_count:
            sentiment = min(1.0, positive_count * 0.3)
        elif negative_count > positive_count:
            sentiment = max(-1.0, -negative_count * 0.3)
        else:
            sentiment = 0.0
        
        return best_type, sentiment
    
    def calculate_relevance(self, title: str, snippet: str, stock_name: str, stock_code: str) -> float:
        """
        计算新闻与股票的相关性
        
        Args:
            title: 新闻标题
            snippet: 新闻摘要
            stock_name: 股票名称
            stock_code: 股票代码
            
        Returns:
            相关性分数 (0-1)
        """
        text = f"{title} {snippet}"
        
        # 检查是否直接提到股票
        if stock_name in text or stock_code in text:
            return 1.0
        
        # 检查是否提到相关行业/概念
        industry_keywords = ['行业', '板块', '领域', '概念']
        if any(kw in text for kw in industry_keywords):
            return 0.6
        
        # 默认相关性
        return 0.3


class AttributionAnalyzer:
    """
    归因分析器
    
    核心功能：
    1. 分析新闻事件与股价变动的关系
    2. 判断主要原因和次要原因
    3. 生成归因描述
    """
    
    # 归因规则：涨跌幅阈值
    SIGNIFICANT_CHANGE_THRESHOLD = 3.0  # 显著变化阈值 (%)
    MAJOR_CHANGE_THRESHOLD = 5.0        # 大幅变化阈值 (%)
    
    # 原因权重映射
    CAUSE_WEIGHTS = {
        NewsEventType.EARNINGS_NEGATIVE: (AttributionCause.EARNINGS_MISS, 0.9),
        NewsEventType.EARNINGS_POSITIVE: (AttributionCause.EARNINGS_MISS, 0.8),
        NewsEventType.INSIDER_SELLING: (AttributionCause.INSIDER_SELLING, 0.85),
        NewsEventType.INSIDER_BUYING: (AttributionCause.INSIDER_SELLING, 0.7),
        NewsEventType.REGULATORY: (AttributionCause.REGULATORY_RISK, 0.95),
        NewsEventType.POLICY_NEGATIVE: (AttributionCause.POLICY_HEADWIND, 0.8),
        NewsEventType.POLICY_POSITIVE: (AttributionCause.POLICY_HEADWIND, 0.7),
        NewsEventType.MARKET_SENTIMENT: (AttributionCause.MARKET_CORRECTION, 0.6),
        NewsEventType.SECTOR_ROTATION: (AttributionCause.SECTOR_ROTATION, 0.5),
    }
    
    def __init__(self):
        self.classifier = NewsEventClassifier()
    
    def analyze(
        self,
        stock_code: str,
        stock_name: str,
        price_change_pct: float,
        news_results: List[Dict[str, Any]],
        sector_name: str = "",
        sector_change_pct: float = 0.0,
        market_change_pct: float = 0.0,
    ) -> AttributionResult:
        """
        执行归因分析
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            price_change_pct: 当日涨跌幅 (%)
            news_results: 新闻搜索结果列表
            sector_name: 所属板块名称
            sector_change_pct: 板块涨跌幅 (%)
            market_change_pct: 大盘涨跌幅 (%)
            
        Returns:
            AttributionResult 归因分析结果
        """
        result = AttributionResult(
            stock_code=stock_code,
            stock_name=stock_name,
            price_change_pct=price_change_pct,
            sector_name=sector_name,
            sector_change_pct=sector_change_pct,
        )
        
        # 判断价格方向
        if price_change_pct > 1.0:
            result.price_direction = "up"
        elif price_change_pct < -1.0:
            result.price_direction = "down"
        else:
            result.price_direction = "neutral"
        
        # 判断相对强度
        if sector_change_pct != 0:
            relative = price_change_pct - sector_change_pct
            if relative > 2.0:
                result.relative_strength = "outperform"
            elif relative < -2.0:
                result.relative_strength = "underperform"
            else:
                result.relative_strength = "neutral"
        
        # 分类新闻事件
        news_events = self._classify_news(news_results, stock_name, stock_code)
        result.related_news = news_events
        
        # 识别主要原因
        primary_cause, confidence, description = self._identify_primary_cause(
            price_change_pct=price_change_pct,
            news_events=news_events,
            sector_change_pct=sector_change_pct,
            market_change_pct=market_change_pct,
        )
        result.primary_cause = primary_cause
        result.primary_cause_confidence = confidence
        result.primary_cause_description = description
        
        # 识别次要原因
        secondary_causes, secondary_descriptions = self._identify_secondary_causes(
            price_change_pct=price_change_pct,
            news_events=news_events,
            primary_cause=primary_cause,
            sector_change_pct=sector_change_pct,
        )
        result.secondary_causes = secondary_causes
        result.secondary_cause_descriptions = secondary_descriptions
        
        # 生成归因描述
        result.attribution_summary = self._generate_summary(result)
        result.action_suggestion = self._generate_suggestion(result)
        
        return result
    
    def _classify_news(
        self,
        news_results: List[Dict[str, Any]],
        stock_name: str,
        stock_code: str
    ) -> List[NewsEvent]:
        """分类新闻事件"""
        events = []
        
        for item in news_results:
            title = item.get('title', '')
            snippet = item.get('snippet', '')
            source = item.get('source', '未知来源')
            published_date = item.get('published_date')
            
            # 分类
            event_type, sentiment = self.classifier.classify(title, snippet)
            
            # 计算相关性
            relevance = self.classifier.calculate_relevance(
                title, snippet, stock_name, stock_code
            )
            
            event = NewsEvent(
                title=title,
                snippet=snippet,
                source=source,
                published_date=published_date,
                event_type=event_type,
                sentiment=sentiment,
                relevance=relevance,
            )
            events.append(event)
        
        return events
    
    def _identify_primary_cause(
        self,
        price_change_pct: float,
        news_events: List[NewsEvent],
        sector_change_pct: float,
        market_change_pct: float,
    ) -> Tuple[AttributionCause, float, str]:
        """识别主要原因"""
        
        # 按相关性和情绪排序新闻
        sorted_events = sorted(
            news_events,
            key=lambda e: (e.relevance, abs(e.sentiment)),
            reverse=True
        )
        
        # 检查是否有高相关性的负面新闻
        for event in sorted_events[:5]:
            if event.relevance >= 0.7 and event.sentiment < -0.3:
                if event.event_type in self.CAUSE_WEIGHTS:
                    cause, weight = self.CAUSE_WEIGHTS[event.event_type]
                    # 根据价格方向调整
                    if price_change_pct < 0 and event.sentiment < 0:
                        confidence = weight * 0.9
                    elif price_change_pct > 0 and event.sentiment > 0:
                        confidence = weight * 0.9
                    else:
                        confidence = weight * 0.6
                    
                    description = self._generate_cause_description(
                        cause, event, price_change_pct
                    )
                    return cause, confidence, description
        
        # 检查是否跟随大盘/板块
        if abs(price_change_pct) > self.SIGNIFICANT_CHANGE_THRESHOLD:
            # 与板块对比
            if sector_change_pct != 0:
                relative = price_change_pct - sector_change_pct
                if abs(relative) < 1.5:
                    # 与板块同步
                    if price_change_pct < 0:
                        cause = AttributionCause.SECTOR_ROTATION
                        confidence = 0.6
                        description = f"该股下跌{abs(price_change_pct):.1f}%，与板块({sector_change_pct:.1f}%)同步回调"
                        return cause, confidence, description
            
            # 与大盘对比
            if market_change_pct != 0:
                relative = price_change_pct - market_change_pct
                if abs(relative) < 1.5:
                    if price_change_pct < 0:
                        cause = AttributionCause.MARKET_CORRECTION
                        confidence = 0.5
                        description = f"该股下跌{abs(price_change_pct):.1f}%，跟随大盘({market_change_pct:.1f}%)回调"
                        return cause, confidence, description
        
        # 检查是否是技术性回调
        if price_change_pct < -self.MAJOR_CHANGE_THRESHOLD:
            cause = AttributionCause.TECHNICAL_BREAKDOWN
            confidence = 0.4
            description = f"该股大幅下跌{abs(price_change_pct):.1f}%，可能存在技术性破位"
            return cause, confidence, description
        
        # 检查是否是获利回吐
        if price_change_pct < -self.SIGNIFICANT_CHANGE_THRESHOLD:
            cause = AttributionCause.PROFIT_TAKING
            confidence = 0.35
            description = f"该股下跌{abs(price_change_pct):.1f}%，可能属于获利回吐"
            return cause, confidence, description
        
        # 无明确原因
        cause = AttributionCause.UNKNOWN
        confidence = 0.2
        description = f"该股涨跌幅{price_change_pct:+.1f}%，无明显利好或利空消息"
        return cause, confidence, description
    
    def _identify_secondary_causes(
        self,
        price_change_pct: float,
        news_events: List[NewsEvent],
        primary_cause: AttributionCause,
        sector_change_pct: float,
    ) -> Tuple[List[AttributionCause], List[str]]:
        """识别次要原因"""
        secondary_causes = []
        secondary_descriptions = []
        
        # 检查板块因素
        if primary_cause != AttributionCause.SECTOR_ROTATION:
            if sector_change_pct != 0:
                relative = price_change_pct - sector_change_pct
                if abs(relative) > 1.5:
                    if price_change_pct < sector_change_pct:
                        secondary_causes.append(AttributionCause.SECTOR_ROTATION)
                        secondary_descriptions.append(
                            f"板块整体{sector_change_pct:+.1f}%，该股显著弱于板块"
                        )
        
        # 检查其他新闻事件
        for event in news_events[:3]:
            if event.event_type in self.CAUSE_WEIGHTS:
                cause, _ = self.CAUSE_WEIGHTS[event.event_type]
                if cause != primary_cause and cause not in secondary_causes:
                    if event.relevance >= 0.5:
                        secondary_causes.append(cause)
                        secondary_descriptions.append(
                            f"存在{event.event_type.value}相关消息"
                        )
        
        return secondary_causes[:3], secondary_descriptions[:3]
    
    def _generate_cause_description(
        self,
        cause: AttributionCause,
        event: NewsEvent,
        price_change_pct: float
    ) -> str:
        """生成原因描述"""
        direction = "下跌" if price_change_pct < 0 else "上涨"
        abs_change = abs(price_change_pct)
        
        if cause == AttributionCause.EARNINGS_MISS:
            return f"该股今日{direction}{abs_change:.1f}%，主要受{event.event_type.value}消息影响"
        elif cause == AttributionCause.INSIDER_SELLING:
            return f"该股今日{direction}{abs_change:.1f}%，主要受减持公告影响"
        elif cause == AttributionCause.REGULATORY_RISK:
            return f"该股今日{direction}{abs_change:.1f}%，主要受监管风险影响"
        elif cause == AttributionCause.POLICY_HEADWIND:
            return f"该股今日{direction}{abs_change:.1f}%，主要受政策因素影响"
        else:
            return f"该股今日{direction}{abs_change:.1f}%"
    
    def _generate_summary(self, result: AttributionResult) -> str:
        """生成归因摘要"""
        lines = []
        
        # 主因
        direction = "下跌" if result.price_change_pct < 0 else "上涨"
        abs_change = abs(result.price_change_pct)
        
        lines.append(
            f"【{result.stock_name}】今日{direction}{abs_change:.1f}%"
        )
        
        if result.primary_cause != AttributionCause.UNKNOWN:
            lines.append(f"主因：{result.primary_cause.value}")
            if result.primary_cause_description:
                lines.append(result.primary_cause_description)
        
        # 板块对比
        if result.sector_name and result.sector_change_pct != 0:
            if result.relative_strength == "underperform":
                lines.append(
                    f"板块【{result.sector_name}】{result.sector_change_pct:+.1f}%，该股显著弱于板块"
                )
            elif result.relative_strength == "outperform":
                lines.append(
                    f"板块【{result.sector_name}】{result.sector_change_pct:+.1f}%，该股强于板块"
                )
        
        # 次要因素
        if result.secondary_causes:
            lines.append(f"次要因素：{', '.join(c.value for c in result.secondary_causes)}")
        
        return "\n".join(lines)
    
    def _generate_suggestion(self, result: AttributionResult) -> str:
        """生成操作建议"""
        cause = result.primary_cause
        price_change = result.price_change_pct
        
        if cause == AttributionCause.EARNINGS_MISS:
            return "建议等待业绩风险释放后再考虑介入"
        elif cause == AttributionCause.INSIDER_SELLING:
            return "减持压力下建议观望，等待减持完成后评估"
        elif cause == AttributionCause.REGULATORY_RISK:
            return "监管风险较高，建议谨慎观望"
        elif cause == AttributionCause.POLICY_HEADWIND:
            return "政策不确定性较高，建议等待政策明朗"
        elif cause == AttributionCause.MARKET_CORRECTION:
            if price_change < -5:
                return "跟随大盘大幅回调，可关注企稳后的低吸机会"
            else:
                return "跟随大盘回调，无需过度担忧"
        elif cause == AttributionCause.TECHNICAL_BREAKDOWN:
            return "技术面破位，建议等待企稳信号"
        elif cause == AttributionCause.PROFIT_TAKING:
            return "获利回吐属正常调整，可关注支撑位企稳情况"
        else:
            return "无明显利空，建议结合技术面判断"


# 便捷函数
_attribution_analyzer: Optional[AttributionAnalyzer] = None


def get_attribution_analyzer() -> AttributionAnalyzer:
    """获取归因分析器单例"""
    global _attribution_analyzer
    if _attribution_analyzer is None:
        _attribution_analyzer = AttributionAnalyzer()
    return _attribution_analyzer


def analyze_attribution(
    stock_code: str,
    stock_name: str,
    price_change_pct: float,
    news_results: List[Dict[str, Any]],
    sector_name: str = "",
    sector_change_pct: float = 0.0,
    market_change_pct: float = 0.0,
) -> AttributionResult:
    """
    便捷函数：执行归因分析
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        price_change_pct: 当日涨跌幅 (%)
        news_results: 新闻搜索结果列表
        sector_name: 所属板块名称
        sector_change_pct: 板块涨跌幅 (%)
        market_change_pct: 大盘涨跌幅 (%)
        
    Returns:
        AttributionResult 归因分析结果
    """
    analyzer = get_attribution_analyzer()
    return analyzer.analyze(
        stock_code=stock_code,
        stock_name=stock_name,
        price_change_pct=price_change_pct,
        news_results=news_results,
        sector_name=sector_name,
        sector_change_pct=sector_change_pct,
        market_change_pct=market_change_pct,
    )


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 模拟新闻数据
    test_news = [
        {
            'title': '某公司股东减持公告',
            'snippet': '控股股东拟减持不超过2%股份',
            'source': '东方财富',
            'published_date': '2026-03-04',
        },
        {
            'title': '中药板块整体回调',
            'snippet': '受市场情绪影响，中药板块今日普遍下跌',
            'source': '同花顺',
            'published_date': '2026-03-05',
        },
    ]
    
    result = analyze_attribution(
        stock_code='300723',
        stock_name='一品红',
        price_change_pct=-4.5,
        news_results=test_news,
        sector_name='中药',
        sector_change_pct=-0.5,
        market_change_pct=-0.8,
    )
    
    print("\n=== 归因分析结果 ===")
    print(result.attribution_summary)
    print(f"\n操作建议：{result.action_suggestion}")