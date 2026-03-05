# -*- coding: utf-8 -*-
"""
Enhanced Analysis Integration Module

Integrates advanced analysis modules into stock analysis workflow:
- LHB Seat Analysis (龙虎榜席位分析)
- Relative Strength (个股vs板块相对强度)
- Market Sentiment (市场温度计)
- Money Effect (赚钱效应监测)
- Sector Rotation (主线轮动图谱)
- Realtime Alert (异动实时推送)

Provides unified API for use in stock analyzer and agent tools.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from .lhb_seat_analyzer import get_lhb_seat_analyzer, LHBSeatAnalysis
from .relative_strength import get_relative_strength_analyzer, RelativeStrengthResult
from .market_sentiment import get_market_sentiment_analyzer, MarketSentimentResult
from .money_effect import get_money_effect_analyzer, MoneyEffectResult
from .sector_rotation import get_sector_rotation_analyzer, SectorRotationResult
from .realtime_alert import get_realtime_alert_scanner, AlertScanResult

logger = logging.getLogger(__name__)


@dataclass
class EnhancedAnalysisResult:
    """Combined result from all enhanced analysis modules"""
    stock_code: str
    stock_name: str
    analysis_date: str
    
    # Individual results
    lhb_analysis: Optional[LHBSeatAnalysis] = None
    relative_strength: Optional[RelativeStrengthResult] = None
    
    # Market context
    market_sentiment: Optional[MarketSentimentResult] = None
    
    # Combined signals
    overall_signal: str = "neutral"           # bullish/bearish/neutral
    confidence: float = 0.5                   # 0-1
    key_findings: List[str] = field(default_factory=list)
    
    # Action suggestions
    primary_action: str = ""                  # hold/buy/sell/watch
    action_reasons: List[str] = field(default_factory=list)


class EnhancedAnalyzer:
    """
    Enhanced Stock Analyzer
    
    Combines multiple analysis dimensions:
    1. LHB Seat Analysis - Track smart money flow
    2. Relative Strength - Compare vs sector
    3. Market Sentiment - Overall market context
    
    Generates unified signals and recommendations.
    """
    
    def __init__(self):
        self.lhb_analyzer = get_lhb_seat_analyzer()
        self.rs_analyzer = get_relative_strength_analyzer()
        self.sentiment_analyzer = get_market_sentiment_analyzer()
        
        # Cache market sentiment (shared across all stocks in same analysis batch)
        self._sentiment_cache: Optional[MarketSentimentResult] = None
        self._sentiment_cache_time: Optional[datetime] = None
    
    def analyze_stock(
        self,
        stock_code: str,
        stock_name: str = "",
        stock_change: float = 0.0,
        include_lhb: bool = True,
        include_rs: bool = True,
        include_sentiment: bool = True,
    ) -> EnhancedAnalysisResult:
        """
        Perform enhanced analysis on a single stock
        
        Args:
            stock_code: Stock code
            stock_name: Stock name (optional)
            stock_change: Today's change percentage
            include_lhb: Whether to include LHB analysis
            include_rs: Whether to include relative strength analysis
            include_sentiment: Whether to include market sentiment
            
        Returns:
            EnhancedAnalysisResult with all requested analysis
        """
        result = EnhancedAnalysisResult(
            stock_code=stock_code,
            stock_name=stock_name,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
        )
        
        # 1. LHB Seat Analysis
        if include_lhb:
            try:
                lhb = self.lhb_analyzer.get_lhb_stock_seats(stock_code)
                result.lhb_analysis = lhb
                logger.debug(f"[增强分析] {stock_code} LHB分析: {lhb.seat_signal if lhb else '无数据'}")
            except Exception as e:
                logger.warning(f"[增强分析] {stock_code} LHB分析失败: {e}")
        
        # 2. Relative Strength Analysis
        if include_rs:
            try:
                rs = self.rs_analyzer.analyze(stock_code, stock_name, stock_change)
                result.relative_strength = rs
                logger.debug(f"[增强分析] {stock_code} 相对强度: {rs.performance_type if rs else '无数据'}")
            except Exception as e:
                logger.warning(f"[增强分析] {stock_code} 相对强度分析失败: {e}")
        
        # 3. Market Sentiment (use cache if available and fresh)
        if include_sentiment:
            try:
                sentiment = self._get_cached_sentiment()
                result.market_sentiment = sentiment
                logger.debug(f"[增强分析] 市场情绪: {sentiment.sentiment_level if sentiment else '无数据'}")
            except Exception as e:
                logger.warning(f"[增强分析] 市场情绪分析失败: {e}")
        
        # 4. Generate combined signals
        self._generate_combined_signals(result)
        
        return result
    
    def _get_cached_sentiment(self, max_age_minutes: int = 30) -> Optional[MarketSentimentResult]:
        """Get market sentiment with caching"""
        now = datetime.now()
        
        # Check if cache is valid
        if (self._sentiment_cache is not None and 
            self._sentiment_cache_time is not None and
            (now - self._sentiment_cache_time).total_seconds() < max_age_minutes * 60):
            return self._sentiment_cache
        
        # Fetch new sentiment
        sentiment = self.sentiment_analyzer.analyze()
        self._sentiment_cache = sentiment
        self._sentiment_cache_time = now
        
        return sentiment
    
    def _generate_combined_signals(self, result: EnhancedAnalysisResult):
        """Generate combined trading signals from all analysis"""
        signals = []
        findings = []
        actions = []
        
        # LHB signals
        if result.lhb_analysis:
            lhb = result.lhb_analysis
            
            if lhb.seat_signal in ["bullish", "slightly_bullish"]:
                signals.append(0.7)
                findings.append(f"🐉 龙虎榜席位偏多: {lhb.signal_reason}")
            elif lhb.seat_signal == "bearish":
                signals.append(-0.5)
                findings.append(f"🐉 龙虎榜席位偏空: {lhb.signal_reason}")
            
            # Known hot money presence
            if lhb.known_seats:
                findings.append(f"⭐ 知名游资参与: {', '.join(lhb.known_seats[:2])}")
            
            # Institution activity
            if lhb.institution_net_buy > 1000:
                signals.append(0.8)
                findings.append(f"🏛️ 机构净买入{lhb.institution_net_buy:.0f}万")
            elif lhb.institution_net_buy < -1000:
                signals.append(-0.6)
                findings.append(f"🏛️ 机构净卖出{abs(lhb.institution_net_buy):.0f}万")
        
        # Relative strength signals
        if result.relative_strength:
            rs = result.relative_strength
            
            if rs.performance_type in ["strong_outperform", "outperform"]:
                signals.append(0.6)
                findings.append(f"📊 相对强度强势: {rs.performance_reason}")
            elif rs.performance_type in ["weak_underperform", "underperform"]:
                signals.append(-0.5)
                findings.append(f"📊 相对强度弱势: {rs.performance_reason}")
            elif rs.performance_type == "contrarian_strong":
                signals.append(0.5)
                findings.append(f"💎 逆势走强: {rs.performance_reason}")
            elif rs.performance_type == "contrarian_weak":
                signals.append(-0.6)
                findings.append(f"⚠️ 与板块背离: {rs.performance_reason}")
            
            if rs.action_hint:
                actions.append(rs.action_hint)
        
        # Market sentiment context
        if result.market_sentiment:
            ms = result.market_sentiment
            
            # Market sentiment affects confidence but not direct signal
            if ms.sentiment_level.value in ["extreme_fear"]:
                findings.append(f"🌡️ 市场极度恐慌，可能存在抄底机会")
            elif ms.sentiment_level.value in ["extreme_greed"]:
                findings.append(f"🌡️ 市场极度贪婪，注意追高风险")
            
            # Add key signals
            for signal in ms.key_signals[:2]:
                findings.append(f"📈 {signal}")
        
        # Calculate overall signal
        if signals:
            avg_signal = sum(signals) / len(signals)
            result.confidence = min(1.0, abs(avg_signal) + 0.3)
            
            if avg_signal >= 0.5:
                result.overall_signal = "bullish"
                result.primary_action = "buy" if avg_signal >= 0.7 else "watch"
            elif avg_signal <= -0.3:
                result.overall_signal = "bearish"
                result.primary_action = "sell" if avg_signal <= -0.5 else "hold"
            else:
                result.overall_signal = "neutral"
                result.primary_action = "hold"
        else:
            result.overall_signal = "neutral"
            result.confidence = 0.3
            result.primary_action = "watch"
        
        result.key_findings = findings
        result.action_reasons = actions
    
    def generate_enhanced_report(self, result: EnhancedAnalysisResult) -> List[str]:
        """
        Generate comprehensive markdown report
        
        Args:
            result: EnhancedAnalysisResult object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"## 🔬 增强分析报告 ({result.stock_name} {result.stock_code})",
            "",
            f"> 分析日期: {result.analysis_date}",
            "",
        ]
        
        # Overall signal
        signal_emoji = {
            "bullish": "🟢",
            "neutral": "🟡",
            "bearish": "🔴",
        }
        emoji = signal_emoji.get(result.overall_signal, "🟡")
        action_emoji = {
            "buy": "📈 买入",
            "watch": "👀 观察",
            "hold": "🤝 持有",
            "sell": "📉 卖出",
        }
        action_text = action_emoji.get(result.primary_action, "👀 观察")
        
        lines.append(f"### 综合信号: {emoji} {result.overall_signal.upper()}")
        lines.append(f"**建议操作**: {action_text} | 置信度: {result.confidence:.0%}")
        lines.append("")
        
        # Key findings
        if result.key_findings:
            lines.append("#### 🔍 关键发现")
            lines.append("")
            for finding in result.key_findings:
                lines.append(f"- {finding}")
            lines.append("")
        
        # LHB analysis
        if result.lhb_analysis:
            lines.append("---")
            lines.append("")
            lhb_lines = self.lhb_analyzer.generate_seat_report(result.lhb_analysis)
            lines.extend(lhb_lines)
        
        # Relative strength
        if result.relative_strength:
            lines.append("---")
            lines.append("")
            rs_lines = self.rs_analyzer.generate_report(result.relative_strength)
            lines.extend(rs_lines)
        
        # Action reasons
        if result.action_reasons:
            lines.append("---")
            lines.append("")
            lines.append("#### 💡 操作建议详情")
            lines.append("")
            for reason in result.action_reasons:
                lines.append(f"- {reason}")
            lines.append("")
        
        return lines
    
    def analyze_market_overview(self) -> Dict[str, Any]:
        """
        Generate market overview analysis
        
        Returns:
            Dict with market sentiment and sector concentration
        """
        result = {
            'sentiment': None,
            'sector_concentration': [],
            'top_sectors': [],
            'bottom_sectors': [],
        }
        
        # Market sentiment
        sentiment = self._get_cached_sentiment()
        result['sentiment'] = sentiment
        
        # Sector concentration from LHB
        try:
            concentration = self.lhb_analyzer.analyze_sector_concentration(days=1)
            result['sector_concentration'] = [
                {
                    'sector': c.sector_name,
                    'count': c.stock_count,
                    'net_buy': c.total_net_buy,
                    'stocks': c.stock_names[:3],
                }
                for c in concentration[:5]
            ]
        except Exception as e:
            logger.warning(f"[增强分析] 板块集中度分析失败: {e}")
        
        return result


# Singleton
_analyzer_instance: Optional[EnhancedAnalyzer] = None


def get_enhanced_analyzer() -> EnhancedAnalyzer:
    """Get EnhancedAnalyzer singleton"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = EnhancedAnalyzer()
    return _analyzer_instance