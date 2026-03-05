# -*- coding: utf-8 -*-
"""
Money-Making Effect Monitor (赚钱效应监测)

Tracks the performance of yesterday's limit-up stocks to gauge market sentiment:
- Yesterday's limit-up stocks performance today
- Success rate of "打板" strategy
- Average return of limit-up stocks
- Money-making effect index (0-100)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class EffectLevel(Enum):
    """Money-making effect levels"""
    EXCELLENT = "excellent"      # Very profitable
    GOOD = "good"                # Profitable
    NORMAL = "normal"            # Break-even
    POOR = "poor"                # Unprofitable
    TERRIBLE = "terrible"        # Very unprofitable


@dataclass
class LimitUpStock:
    """A stock that hit limit-up yesterday"""
    code: str
    name: str
    yesterday_close: float           # 昨日收盘价（涨停价）
    today_open: float = 0.0          # 今日开盘价
    today_high: float = 0.0          # 今日最高价
    today_low: float = 0.0           # 今日最低价
    today_close: float = 0.0         # 今日收盘价
    today_change_pct: float = 0.0    # 今日涨跌幅
    max_return: float = 0.0          # 最大收益（从涨停价算）
    is_success: bool = False         # 是否成功（收盘上涨）
    hit_limit_up: bool = False       # 是否连板
    sector: str = ""                 # 所属板块


@dataclass
class MoneyEffectResult:
    """Money-making effect analysis result"""
    analysis_date: str
    
    # Yesterday's limit-up stocks
    limit_up_stocks: List[LimitUpStock] = field(default_factory=list)
    total_count: int = 0                  # 昨日涨停总数
    success_count: int = 0                # 今日上涨家数
    limit_up_again_count: int = 0         # 连板家数
    
    # Metrics
    avg_return: float = 0.0               # 平均收益率
    avg_max_return: float = 0.0           # 平均最大收益
    success_rate: float = 0.0             # 成功率（收盘上涨）
    limit_up_again_rate: float = 0.0      # 连板率
    
    # Index
    effect_score: float = 50.0            # 赚钱效应指数 (0-100)
    effect_level: EffectLevel = EffectLevel.NORMAL
    
    # Trading suggestion
    trading_hint: str = ""
    risk_warning: str = ""
    
    # Sector analysis
    sector_performance: List[Dict[str, Any]] = field(default_factory=list)


class MoneyEffectAnalyzer:
    """
    Money-Making Effect Analyzer
    
    Analyzes how yesterday's limit-up stocks performed today.
    This is a crucial indicator for short-term traders to gauge
    whether the "打板" strategy is profitable.
    
    Key Metrics:
    - Success Rate: % of yesterday's limit-up stocks that closed up today
    - Average Return: Average performance of yesterday's limit-up stocks
    - Double Limit-Up Rate: % that hit limit-up again (连板)
    """
    
    def __init__(self):
        self._akshare = None
        self._cache = {}
    
    def _get_akshare(self):
        """Lazy import akshare"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare
    
    def get_yesterday_limit_up_stocks(self) -> List[LimitUpStock]:
        """
        Get list of stocks that hit limit-up yesterday
        
        Uses akshare stock_zt_pool_em API (涨停池)
        """
        ak = self._get_akshare()
        
        try:
            logger.info("[赚钱效应] 获取昨日涨停股票列表...")
            
            # Get limit-up pool (涨停池)
            df = ak.stock_zt_pool_em(date=None)  # None means latest trading day
            
            if df is None or df.empty:
                logger.warning("[赚钱效应] 未获取到涨停池数据")
                return []
            
            stocks = []
            for _, row in df.iterrows():
                try:
                    stock = LimitUpStock(
                        code=str(row.get('代码', '')),
                        name=str(row.get('名称', '')),
                        yesterday_close=float(row.get('涨停价', row.get('最新价', 0))),
                        sector=str(row.get('所属行业', '')),
                    )
                    stocks.append(stock)
                except Exception as e:
                    logger.debug(f"[赚钱效应] 解析涨停股失败: {e}")
                    continue
            
            logger.info(f"[赚钱效应] 获取到 {len(stocks)} 只昨日涨停股")
            return stocks
            
        except Exception as e:
            logger.error(f"[赚钱效应] 获取涨停池失败: {e}")
            return []
    
    def get_today_performance(self, stock: LimitUpStock) -> Optional[LimitUpStock]:
        """
        Get today's performance for a limit-up stock
        
        Args:
            stock: LimitUpStock with yesterday's data
            
        Returns:
            Updated LimitUpStock with today's performance
        """
        ak = self._get_akshare()
        
        try:
            # Get real-time quote
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return None
            
            row = df[df['代码'] == stock.code]
            if row.empty:
                return None
            
            row = row.iloc[0]
            
            stock.today_open = float(row.get('今开', 0))
            stock.today_high = float(row.get('最高', 0))
            stock.today_low = float(row.get('最低', 0))
            stock.today_close = float(row.get('最新价', 0))
            stock.today_change_pct = float(row.get('涨跌幅', 0))
            
            # Calculate max return from yesterday's limit-up price
            if stock.yesterday_close > 0:
                stock.max_return = (stock.today_high - stock.yesterday_close) / stock.yesterday_close * 100
            
            # Check if success (closed up)
            stock.is_success = stock.today_change_pct > 0
            
            # Check if hit limit-up again (连板)
            stock.hit_limit_up = stock.today_change_pct >= 9.9
            
            return stock
            
        except Exception as e:
            logger.debug(f"[赚钱效应] 获取 {stock.code} 今日表现失败: {e}")
            return None
    
    def analyze(self) -> MoneyEffectResult:
        """
        Perform money-making effect analysis
        
        Returns:
            MoneyEffectResult with all metrics
        """
        result = MoneyEffectResult(
            analysis_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        # Get yesterday's limit-up stocks
        limit_up_stocks = self.get_yesterday_limit_up_stocks()
        
        if not limit_up_stocks:
            logger.warning("[赚钱效应] 无涨停股数据，返回默认结果")
            result.trading_hint = "无涨停股数据，无法计算赚钱效应"
            return result
        
        # Get today's performance for each stock
        updated_stocks = []
        for stock in limit_up_stocks:
            updated = self.get_today_performance(stock)
            if updated:
                updated_stocks.append(updated)
        
        result.limit_up_stocks = updated_stocks
        result.total_count = len(updated_stocks)
        
        if result.total_count == 0:
            return result
        
        # Calculate metrics
        result.success_count = sum(1 for s in updated_stocks if s.is_success)
        result.limit_up_again_count = sum(1 for s in updated_stocks if s.hit_limit_up)
        
        result.success_rate = result.success_count / result.total_count * 100
        result.limit_up_again_rate = result.limit_up_again_count / result.total_count * 100
        
        # Average returns
        returns = [s.today_change_pct for s in updated_stocks]
        max_returns = [s.max_return for s in updated_stocks]
        
        result.avg_return = sum(returns) / len(returns) if returns else 0
        result.avg_max_return = sum(max_returns) / len(max_returns) if max_returns else 0
        
        # Calculate effect score (0-100)
        result.effect_score = self._calculate_effect_score(result)
        
        # Determine effect level
        result.effect_level = self._determine_effect_level(result.effect_score)
        
        # Generate trading hints
        result.trading_hint = self._generate_trading_hint(result)
        result.risk_warning = self._generate_risk_warning(result)
        
        # Sector analysis
        result.sector_performance = self._analyze_sectors(updated_stocks)
        
        logger.info(f"[赚钱效应] 评分: {result.effect_score:.1f}, 成功率: {result.success_rate:.1f}%, "
                   f"连板率: {result.limit_up_again_rate:.1f}%")
        
        return result
    
    def _calculate_effect_score(self, result: MoneyEffectResult) -> float:
        """
        Calculate money-making effect score (0-100)
        
        Components:
        - Success rate (40%): % of stocks that closed up
        - Average return (30%): How much money was made on average
        - Double limit-up rate (20%): % of stocks that hit limit-up again
        - Max return potential (10%): Average max return opportunity
        """
        # Success rate component (0-40 points)
        success_score = result.success_rate * 0.4
        
        # Average return component (0-30 points)
        # Scale: -10% -> 0 points, +5% -> 30 points
        avg_return_score = max(0, min(30, (result.avg_return + 10) / 15 * 30))
        
        # Double limit-up rate component (0-20 points)
        limit_up_score = result.limit_up_again_rate * 0.2
        
        # Max return potential component (0-10 points)
        # Scale: 0% -> 5 points, 10% -> 10 points
        max_return_score = max(0, min(10, result.avg_max_return))
        
        total_score = success_score + avg_return_score + limit_up_score + max_return_score
        
        return min(100, max(0, total_score))
    
    def _determine_effect_level(self, score: float) -> EffectLevel:
        """Determine effect level based on score"""
        if score >= 80:
            return EffectLevel.EXCELLENT
        elif score >= 60:
            return EffectLevel.GOOD
        elif score >= 40:
            return EffectLevel.NORMAL
        elif score >= 20:
            return EffectLevel.POOR
        else:
            return EffectLevel.TERRIBLE
    
    def _generate_trading_hint(self, result: MoneyEffectResult) -> str:
        """Generate trading hint based on analysis"""
        level = result.effect_level
        
        if level == EffectLevel.EXCELLENT:
            return (f"赚钱效应极佳！昨日涨停股今日平均收益{result.avg_return:+.1f}%，"
                   f"连板率{result.limit_up_again_rate:.0f}%。打板策略收益丰厚，可积极参与热点题材。")
        
        elif level == EffectLevel.GOOD:
            return (f"赚钱效应良好。昨日涨停股成功率{result.success_rate:.0f}%，"
                   f"平均收益{result.avg_return:+.1f}%。可适度参与强势股，注意去弱留强。")
        
        elif level == EffectLevel.NORMAL:
            return (f"赚钱效应一般。昨日涨停股成功率{result.success_rate:.0f}%，"
                   f"平均收益{result.avg_return:+.1f}%。打板需谨慎，优选板块龙头。")
        
        elif level == EffectLevel.POOR:
            return (f"赚钱效应较差。昨日涨停股成功率仅{result.success_rate:.0f}%，"
                   f"平均收益{result.avg_return:+.1f}%。建议收缩战线，减少打板操作。")
        
        else:  # TERRIBLE
            return (f"赚钱效应极差！昨日涨停股成功率仅{result.success_rate:.0f}%，"
                   f"平均亏损{abs(result.avg_return):.1f}%。强烈建议空仓观望，避免追高。")
    
    def _generate_risk_warning(self, result: MoneyEffectResult) -> str:
        """Generate risk warning based on analysis"""
        warnings = []
        
        if result.avg_return < -3:
            warnings.append("⚠️ 打板亏钱效应明显，追高风险极大")
        
        if result.success_rate < 30:
            warnings.append("⚠️ 涨停股次日成功率极低，市场情绪低迷")
        
        if result.limit_up_again_count == 0 and result.total_count > 10:
            warnings.append("⚠️ 无连板股，市场接力意愿弱")
        
        if result.avg_max_return > 5 and result.avg_return < 0:
            warnings.append("⚠️ 盘中冲高回落多，日内追高易被套")
        
        if not warnings:
            warnings.append("市场情绪正常，注意控制仓位")
        
        return " | ".join(warnings)
    
    def _analyze_sectors(self, stocks: List[LimitUpStock]) -> List[Dict[str, Any]]:
        """Analyze which sectors have the most limit-up stocks"""
        sector_count: Dict[str, List[LimitUpStock]] = {}
        
        for stock in stocks:
            sector = stock.sector or "其他"
            if sector not in sector_count:
                sector_count[sector] = []
            sector_count[sector].append(stock)
        
        # Sort by count
        sorted_sectors = sorted(sector_count.items(), key=lambda x: len(x[1]), reverse=True)
        
        result = []
        for sector, stocks_list in sorted_sectors[:5]:
            success_count = sum(1 for s in stocks_list if s.is_success)
            avg_return = sum(s.today_change_pct for s in stocks_list) / len(stocks_list)
            
            result.append({
                'sector': sector,
                'count': len(stocks_list),
                'success_count': success_count,
                'success_rate': success_count / len(stocks_list) * 100,
                'avg_return': avg_return,
                'stocks': [{'code': s.code, 'name': s.name, 'change': s.today_change_pct} 
                          for s in stocks_list[:3]],
            })
        
        return result
    
    def generate_report(self, result: MoneyEffectResult) -> List[str]:
        """
        Generate markdown report for money-making effect
        
        Args:
            result: MoneyEffectResult object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"## 💰 赚钱效应监测 ({result.analysis_date})",
            "",
        ]
        
        # Effect score bar
        level_colors = {
            EffectLevel.EXCELLENT: "🟢🟢",
            EffectLevel.GOOD: "🟢",
            EffectLevel.NORMAL: "🟡",
            EffectLevel.POOR: "🔴",
            EffectLevel.TERRIBLE: "🔴🔴",
        }
        
        level_names = {
            EffectLevel.EXCELLENT: "极佳",
            EffectLevel.GOOD: "良好",
            EffectLevel.NORMAL: "一般",
            EffectLevel.POOR: "较差",
            EffectLevel.TERRIBLE: "极差",
        }
        
        color = level_colors.get(result.effect_level, "🟡")
        name = level_names.get(result.effect_level, "一般")
        
        # Score bar
        bar_len = 20
        filled = int(result.effect_score / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        lines.append(f"### 赚钱效应指数: {result.effect_score:.0f} {color}")
        lines.append(f"`[{bar}]` {name}")
        lines.append("")
        
        # Summary
        lines.append(f"> {result.trading_hint}")
        lines.append("")
        
        # Key metrics table
        if result.total_count > 0:
            lines.append("#### 📊 核心指标")
            lines.append("")
            lines.append("| 指标 | 数值 | 解读 |")
            lines.append("|------|------|------|")
            
            # Success rate
            sr_emoji = "✅" if result.success_rate >= 50 else "❌"
            lines.append(f"| 涨停股成功率 | {result.success_rate:.1f}% | {sr_emoji} {'过半上涨' if result.success_rate >= 50 else '多数下跌'} |")
            
            # Average return
            ar_emoji = "📈" if result.avg_return > 0 else "📉"
            lines.append(f"| 平均收益率 | {result.avg_return:+.2f}% | {ar_emoji} {'赚钱' if result.avg_return > 0 else '亏钱'} |")
            
            # Double limit-up rate
            lines.append(f"| 连板率 | {result.limit_up_again_rate:.1f}% | {'🔥 接力活跃' if result.limit_up_again_rate >= 20 else '⚠️ 接力谨慎'} |")
            
            # Max return
            lines.append(f"| 平均最大收益 | {result.avg_max_return:+.2f}% | {'日内机会多' if result.avg_max_return > 3 else '日内机会少'} |")
            
            lines.append("")
            
            # Statistics
            lines.append(f"> 昨日涨停 {result.total_count} 只，今日上涨 {result.success_count} 只，连板 {result.limit_up_again_count} 只")
            lines.append("")
        
        # Risk warning
        lines.append("#### ⚠️ 风险提示")
        lines.append("")
        lines.append(result.risk_warning)
        lines.append("")
        
        # Sector performance
        if result.sector_performance:
            lines.append("#### 🏭 板块表现")
            lines.append("")
            lines.append("| 板块 | 涨停数 | 成功率 | 平均收益 | 代表股 |")
            lines.append("|------|--------|--------|----------|--------|")
            
            for sp in result.sector_performance:
                stocks_str = ", ".join([f"{s['name']}" for s in sp['stocks'][:2]])
                lines.append(f"| {sp['sector']} | {sp['count']} | {sp['success_rate']:.0f}% | "
                           f"{sp['avg_return']:+.1f}% | {stocks_str} |")
            
            lines.append("")
        
        return lines


# Singleton
_analyzer_instance: Optional[MoneyEffectAnalyzer] = None


def get_money_effect_analyzer() -> MoneyEffectAnalyzer:
    """Get MoneyEffectAnalyzer singleton"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = MoneyEffectAnalyzer()
    return _analyzer_instance