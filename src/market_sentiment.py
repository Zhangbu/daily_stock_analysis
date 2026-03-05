# -*- coding: utf-8 -*-
"""
Market Sentiment Thermometer (市场温度计)

Provides comprehensive market sentiment analysis:
- Composite sentiment index (0-100: Fear to Greed)
- Up/Down/Limit statistics
- Northbound capital flow
- Margin trading data
- Money-making effect metrics
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Market sentiment levels"""
    EXTREME_FEAR = "extreme_fear"      # 0-20
    FEAR = "fear"                       # 20-40
    NEUTRAL = "neutral"                 # 40-60
    GREED = "greed"                     # 60-80
    EXTREME_GREED = "extreme_greed"     # 80-100


@dataclass
class MarketStats:
    """Raw market statistics"""
    total_stocks: int = 0              # 总股票数
    up_count: int = 0                  # 上涨家数
    down_count: int = 0                # 下跌家数
    flat_count: int = 0                # 平盘家数
    limit_up_count: int = 0            # 涨停家数
    limit_down_count: int = 0          # 跌停家数
    
    # Amounts
    total_amount: float = 0.0          # 总成交额（亿）
    
    # Key ratios
    up_ratio: float = 0.0              # 上涨比例
    limit_up_ratio: float = 0.0        # 涨停比例
    
    # Change from previous day
    limit_up_change: int = 0           # 涨停家数变化
    limit_down_change: int = 0         # 跌停家数变化


@dataclass
class NorthboundFlow:
    """Northbound capital flow data"""
    sh_flow: float = 0.0              # 沪股通净流入（亿）
    sz_flow: float = 0.0              # 深股通净流入（亿）
    total_flow: float = 0.0           # 总净流入（亿）
    
    # Trend
    is_inflow: bool = True            # 是否净流入
    flow_trend: str = "neutral"       # continuous_inflow/continuous_outflow/neutral


@dataclass
class MarginData:
    """Margin trading data"""
    margin_balance: float = 0.0       # 融资余额（亿）
    margin_change: float = 0.0        # 融资余额变化（亿）
    
    short_balance: float = 0.0        # 融券余额（亿）
    short_change: float = 0.0         # 融券余额变化（亿）
    
    # Trend
    margin_trend: str = "stable"      # increasing/decreasing/stable


@dataclass
class MoneyMakingEffect:
    """Money-making effect metrics"""
    yesterday_limit_up_return: float = 0.0    # 昨日涨停股今日平均收益
    yesterday_limit_up_success: float = 0.0   # 昨日涨停股今日成功率
    avg_amplitude: float = 0.0                # 平均振幅
    avg_turnover: float = 0.0                 # 平均换手率
    
    # Rating
    effect_level: str = "neutral"             # good/normal/bad/terrible
    effect_score: float = 50.0                # 0-100


@dataclass
class MarketSentimentResult:
    """Complete market sentiment analysis result"""
    analysis_date: str
    
    # Components
    market_stats: Optional[MarketStats] = None
    northbound_flow: Optional[NorthboundFlow] = None
    margin_data: Optional[MarginData] = None
    money_effect: Optional[MoneyMakingEffect] = None
    
    # Composite score
    sentiment_score: float = 50.0           # 0-100: Fear to Greed
    sentiment_level: SentimentLevel = SentimentLevel.NEUTRAL
    
    # Component scores
    breadth_score: float = 50.0             # 市场宽度得分
    momentum_score: float = 50.0            # 动量得分
    flow_score: float = 50.0                # 资金流向得分
    margin_score: float = 50.0              # 融资融券得分
    
    # Summary
    summary: str = ""
    key_signals: List[str] = field(default_factory=list)
    
    # Action suggestion
    position_advice: str = ""


class MarketSentimentAnalyzer:
    """
    Market Sentiment Analyzer
    
    Analyzes overall market sentiment using multiple indicators:
    1. Market breadth (up/down/limit statistics)
    2. Northbound capital flow
    3. Margin trading data
    4. Money-making effect (昨日涨停表现)
    
    Generates a composite 0-100 sentiment score.
    """
    
    # Historical averages for normalization
    AVG_LIMIT_UP = 50          # 平均涨停数
    AVG_LIMIT_DOWN = 30        # 平均跌停数
    AVG_UP_RATIO = 0.5         # 平均上涨比例
    AVG_NORTHBOUND = 0.0       # 平均北向净流入
    
    def __init__(self):
        self._akshare = None
        self._cache = {}
    
    def _get_akshare(self):
        """Lazy import akshare"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare
    
    def get_market_stats(self) -> Optional[MarketStats]:
        """
        Get market breadth statistics
        
        Uses akshare stock_zh_a_spot_em API
        """
        ak = self._get_akshare()
        
        try:
            logger.info("[市场温度计] 获取市场涨跌统计...")
            df = ak.stock_zh_a_spot_em()
            
            if df is None or df.empty:
                return None
            
            stats = MarketStats()
            stats.total_stocks = len(df)
            
            # Calculate statistics
            change_col = '涨跌幅'
            df[change_col] = df[change_col].astype(float)
            
            stats.up_count = len(df[df[change_col] > 0])
            stats.down_count = len(df[df[change_col] < 0])
            stats.flat_count = len(df[df[change_col] == 0])
            stats.limit_up_count = len(df[df[change_col] >= 9.9])
            stats.limit_down_count = len(df[df[change_col] <= -9.9])
            
            # Calculate amounts
            if '成交额' in df.columns:
                stats.total_amount = df['成交额'].sum() / 1e8  # Convert to 亿
            
            # Calculate ratios
            stats.up_ratio = stats.up_count / stats.total_stocks if stats.total_stocks > 0 else 0
            stats.limit_up_ratio = stats.limit_up_count / stats.total_stocks if stats.total_stocks > 0 else 0
            
            logger.info(f"[市场温度计] 上涨{stats.up_count}家, 下跌{stats.down_count}家, "
                       f"涨停{stats.limit_up_count}只, 跌停{stats.limit_down_count}只")
            
            return stats
            
        except Exception as e:
            logger.error(f"[市场温度计] 获取市场统计失败: {e}")
            return None
    
    def get_northbound_flow(self) -> Optional[NorthboundFlow]:
        """
        Get northbound capital flow data
        
        Uses akshare stock_hsgt_north_net_flow_in_em API
        """
        ak = self._get_akshare()
        
        try:
            logger.info("[市场温度计] 获取北向资金流向...")
            
            # Get recent northbound flow
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            
            if df is None or df.empty:
                return None
            
            # Get latest data
            latest = df.iloc[-1]
            
            flow = NorthboundFlow()
            flow.total_flow = float(latest.get('当日净流入', 0))
            
            # Determine trend
            flow.is_inflow = flow.total_flow > 0
            
            # Check if continuous inflow/outflow
            if len(df) >= 3:
                recent_3d = df.tail(3)
                all_positive = all(recent_3d['当日净流入'].astype(float) > 0)
                all_negative = all(recent_3d['当日净流入'].astype(float) < 0)
                
                if all_positive:
                    flow.flow_trend = "continuous_inflow"
                elif all_negative:
                    flow.flow_trend = "continuous_outflow"
                else:
                    flow.flow_trend = "neutral"
            
            logger.info(f"[市场温度计] 北向资金净流入: {flow.total_flow:.2f}亿, 趋势: {flow.flow_trend}")
            
            return flow
            
        except Exception as e:
            logger.warning(f"[市场温度计] 获取北向资金失败: {e}")
            return None
    
    def get_margin_data(self) -> Optional[MarginData]:
        """
        Get margin trading data
        
        Uses akshare stock_margin_detail_szse API (simplified)
        """
        ak = self._get_akshare()
        
        try:
            logger.info("[市场温度计] 获取融资融券数据...")
            
            # Get margin data for both exchanges
            # Note: This is simplified, actual implementation may need adjustment
            margin = MarginData()
            
            try:
                # Try to get latest margin data
                # akshare has multiple margin APIs
                df = ak.stock_margin_detail_szse()
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    margin.margin_balance = float(latest.get('融资余额', 0)) / 1e8
            except Exception:
                pass
            
            # Set trend based on data availability
            margin.margin_trend = "stable"
            
            logger.info(f"[市场温度计] 融资余额: {margin.margin_balance:.2f}亿")
            
            return margin
            
        except Exception as e:
            logger.warning(f"[市场温度计] 获取融资融券失败: {e}")
            return None
    
    def get_money_making_effect(self) -> Optional[MoneyMakingEffect]:
        """
        Calculate money-making effect
        
        Analyzes how yesterday's limit-up stocks performed today.
        This is a key indicator for short-term trading.
        """
        ak = self._get_akshare()
        
        try:
            logger.info("[市场温度计] 计算赚钱效应...")
            
            effect = MoneyMakingEffect()
            
            # Get yesterday's limit-up stocks
            # This requires tracking limit-up stocks across days
            # Simplified: use sector performance as proxy
            
            try:
                # Get market stats for average amplitude
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    if '振幅' in df.columns:
                        effect.avg_amplitude = df['振幅'].astype(float).mean()
                    if '换手率' in df.columns:
                        effect.avg_turnover = df['换手率'].astype(float).mean()
            except Exception:
                pass
            
            # Estimate effect based on market conditions
            # In production, should track actual limit-up stocks
            effect.yesterday_limit_up_return = 0.0  # Placeholder
            effect.yesterday_limit_up_success = 0.0  # Placeholder
            
            # Classify effect level
            if effect.avg_amplitude > 5:
                effect.effect_level = "good"
                effect.effect_score = 70
            elif effect.avg_amplitude > 3:
                effect.effect_level = "normal"
                effect.effect_score = 50
            else:
                effect.effect_level = "bad"
                effect.effect_score = 30
            
            logger.info(f"[市场温度计] 赚钱效应: {effect.effect_level}, 平均振幅: {effect.avg_amplitude:.2f}%")
            
            return effect
            
        except Exception as e:
            logger.warning(f"[市场温度计] 计算赚钱效应失败: {e}")
            return None
    
    def calculate_sentiment_score(
        self,
        market_stats: Optional[MarketStats],
        northbound_flow: Optional[NorthboundFlow],
        margin_data: Optional[MarginData],
        money_effect: Optional[MoneyMakingEffect],
    ) -> Tuple[float, SentimentLevel]:
        """
        Calculate composite sentiment score (0-100)
        
        Components:
        - Market breadth: 40%
        - Northbound flow: 30%
        - Money-making effect: 20%
        - Margin data: 10%
        """
        scores = []
        
        # 1. Market breadth score (40%)
        if market_stats:
            # Up ratio score
            up_score = market_stats.up_ratio * 100
            
            # Limit up vs limit down
            limit_ratio = (market_stats.limit_up_count - market_stats.limit_down_count) / max(market_stats.total_stocks, 1)
            limit_score = 50 + limit_ratio * 500  # Scale
            
            breadth_score = (up_score * 0.6 + limit_score * 0.4)
            scores.append(('breadth', breadth_score, 0.4))
        else:
            scores.append(('breadth', 50, 0.4))
        
        # 2. Northbound flow score (30%)
        if northbound_flow:
            # Scale flow to score
            # Large inflow (>50亿) = 80-100
            # Moderate inflow (10-50亿) = 60-80
            # Neutral = 40-60
            # Outflow = 20-40
            # Large outflow = 0-20
            
            flow = northbound_flow.total_flow
            if flow > 50:
                flow_score = 90
            elif flow > 10:
                flow_score = 60 + (flow - 10) * 0.5
            elif flow > -10:
                flow_score = 50 + flow * 0.5
            elif flow > -50:
                flow_score = 30 + (flow + 10) * 0.25
            else:
                flow_score = 10
            
            # Adjust for trend
            if northbound_flow.flow_trend == "continuous_inflow":
                flow_score = min(100, flow_score + 10)
            elif northbound_flow.flow_trend == "continuous_outflow":
                flow_score = max(0, flow_score - 10)
            
            scores.append(('flow', flow_score, 0.3))
        else:
            scores.append(('flow', 50, 0.3))
        
        # 3. Money-making effect score (20%)
        if money_effect:
            effect_score = money_effect.effect_score
            scores.append(('effect', effect_score, 0.2))
        else:
            scores.append(('effect', 50, 0.2))
        
        # 4. Margin score (10%)
        if margin_data:
            # Increasing margin balance = bullish
            margin_score = 50  # Neutral default
            if margin_data.margin_change > 0:
                margin_score = 60
            elif margin_data.margin_change < 0:
                margin_score = 40
            scores.append(('margin', margin_score, 0.1))
        else:
            scores.append(('margin', 50, 0.1))
        
        # Calculate weighted average
        total_score = sum(score * weight for _, score, weight in scores)
        
        # Determine level
        if total_score >= 80:
            level = SentimentLevel.EXTREME_GREED
        elif total_score >= 60:
            level = SentimentLevel.GREED
        elif total_score >= 40:
            level = SentimentLevel.NEUTRAL
        elif total_score >= 20:
            level = SentimentLevel.FEAR
        else:
            level = SentimentLevel.EXTREME_FEAR
        
        return total_score, level
    
    def analyze(self) -> MarketSentimentResult:
        """
        Perform complete market sentiment analysis
        
        Returns:
            MarketSentimentResult with all components
        """
        result = MarketSentimentResult(
            analysis_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        # Get all components
        result.market_stats = self.get_market_stats()
        result.northbound_flow = self.get_northbound_flow()
        result.margin_data = self.get_margin_data()
        result.money_effect = self.get_money_making_effect()
        
        # Calculate composite score
        score, level = self.calculate_sentiment_score(
            result.market_stats,
            result.northbound_flow,
            result.margin_data,
            result.money_effect,
        )
        
        result.sentiment_score = score
        result.sentiment_level = level
        
        # Generate summary and signals
        result.summary = self._generate_summary(result)
        result.key_signals = self._extract_key_signals(result)
        result.position_advice = self._generate_position_advice(result)
        
        return result
    
    def _generate_summary(self, result: MarketSentimentResult) -> str:
        """Generate sentiment summary text"""
        level_names = {
            SentimentLevel.EXTREME_FEAR: "极度恐慌",
            SentimentLevel.FEAR: "恐慌",
            SentimentLevel.NEUTRAL: "中性",
            SentimentLevel.GREED: "贪婪",
            SentimentLevel.EXTREME_GREED: "极度贪婪",
        }
        
        level_name = level_names.get(result.sentiment_level, "中性")
        
        parts = [f"市场情绪指数 {result.sentiment_score:.0f} 分，处于「{level_name}」区间"]
        
        if result.market_stats:
            ms = result.market_stats
            parts.append(f"涨跌比 {ms.up_count}:{ms.down_count}，涨停{ms.limit_up_count}只，跌停{ms.limit_down_count}只")
        
        if result.northbound_flow:
            nb = result.northbound_flow
            flow_str = "净流入" if nb.is_inflow else "净流出"
            parts.append(f"北向资金{flow_str}{abs(nb.total_flow):.1f}亿")
        
        return "。".join(parts) + "。"
    
    def _extract_key_signals(self, result: MarketSentimentResult) -> List[str]:
        """Extract key signals from analysis"""
        signals = []
        
        if result.market_stats:
            ms = result.market_stats
            
            # High limit-up count
            if ms.limit_up_count >= 80:
                signals.append(f"🔥 涨停家数{ms.limit_up_count}只，赚钱效应火爆")
            elif ms.limit_up_count <= 20:
                signals.append(f"❄️ 涨停仅{ms.limit_up_count}只，市场低迷")
            
            # Limit down warning
            if ms.limit_down_count >= 50:
                signals.append(f"⚠️ 跌停{ms.limit_down_count}只，市场恐慌情绪浓重")
            
            # Up ratio extremes
            if ms.up_ratio >= 0.7:
                signals.append(f"📈 上涨比例{ms.up_ratio:.0%}，普涨行情")
            elif ms.up_ratio <= 0.3:
                signals.append(f"📉 上涨比例仅{ms.up_ratio:.0%}，普跌行情")
        
        if result.northbound_flow:
            nb = result.northbound_flow
            
            if nb.total_flow > 50:
                signals.append(f"💰 北向大举净流入{nb.total_flow:.0f}亿，外资看好")
            elif nb.total_flow < -50:
                signals.append(f"💸 北向大举净流出{abs(nb.total_flow):.0f}亿，外资撤离")
            
            if nb.flow_trend == "continuous_inflow":
                signals.append("🔄 北向连续3日净流入，趋势向好")
            elif nb.flow_trend == "continuous_outflow":
                signals.append("🔄 北向连续3日净流出，需警惕")
        
        return signals
    
    def _generate_position_advice(self, result: MarketSentimentResult) -> str:
        """Generate position advice based on sentiment"""
        score = result.sentiment_score
        
        if score >= 80:
            return "情绪极度贪婪，市场过热，建议逐步减仓，锁定利润"
        elif score >= 60:
            return "情绪偏乐观，可维持当前仓位，追高需谨慎"
        elif score >= 40:
            return "情绪中性，可保持观望，等待更明确信号"
        elif score >= 20:
            return "情绪恐慌，可逐步低吸优质标的，分批建仓"
        else:
            return "情绪极度恐慌，市场可能见底，可积极布局"
    
    def generate_report(self, result: MarketSentimentResult) -> List[str]:
        """
        Generate markdown report for market sentiment
        
        Args:
            result: MarketSentimentResult object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"## 🌡️ 市场温度计 ({result.analysis_date})",
            "",
        ]
        
        # Sentiment meter
        level_colors = {
            SentimentLevel.EXTREME_FEAR: "🔴🔴",
            SentimentLevel.FEAR: "🔴",
            SentimentLevel.NEUTRAL: "🟡",
            SentimentLevel.GREED: "🟢",
            SentimentLevel.EXTREME_GREED: "🟢🟢",
        }
        
        level_names = {
            SentimentLevel.EXTREME_FEAR: "极度恐慌",
            SentimentLevel.FEAR: "恐慌",
            SentimentLevel.NEUTRAL: "中性",
            SentimentLevel.GREED: "贪婪",
            SentimentLevel.EXTREME_GREED: "极度贪婪",
        }
        
        color = level_colors.get(result.sentiment_level, "🟡")
        name = level_names.get(result.sentiment_level, "中性")
        
        # Score bar
        bar_len = 20
        filled = int(result.sentiment_score / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        lines.append(f"### 情绪指数: {result.sentiment_score:.0f} {color}")
        lines.append(f"`[{bar}]` {name}")
        lines.append("")
        
        # Summary
        lines.append(f"> {result.summary}")
        lines.append("")
        
        # Key signals
        if result.key_signals:
            lines.append("#### 📊 关键信号")
            lines.append("")
            for signal in result.key_signals:
                lines.append(f"- {signal}")
            lines.append("")
        
        # Market stats table
        if result.market_stats:
            ms = result.market_stats
            lines.append("#### 📈 市场统计")
            lines.append("")
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            lines.append(f"| 上涨家数 | {ms.up_count} ({ms.up_ratio:.0%}) |")
            lines.append(f"| 下跌家数 | {ms.down_count} |")
            lines.append(f"| 涨停家数 | {ms.limit_up_count} |")
            lines.append(f"| 跌停家数 | {ms.limit_down_count} |")
            lines.append(f"| 总成交额 | {ms.total_amount:.0f}亿 |")
            lines.append("")
        
        # Northbound flow
        if result.northbound_flow:
            nb = result.northbound_flow
            flow_str = "净流入" if nb.is_inflow else "净流出"
            lines.append(f"#### 💰 北向资金: {flow_str} {abs(nb.total_flow):.1f}亿")
            lines.append("")
        
        # Position advice
        lines.append("#### 💡 仓位建议")
        lines.append("")
        lines.append(result.position_advice)
        lines.append("")
        
        return lines


# Singleton
_analyzer_instance: Optional[MarketSentimentAnalyzer] = None


def get_market_sentiment_analyzer() -> MarketSentimentAnalyzer:
    """Get MarketSentimentAnalyzer singleton"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = MarketSentimentAnalyzer()
    return _analyzer_instance