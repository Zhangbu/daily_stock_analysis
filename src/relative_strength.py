# -*- coding: utf-8 -*-
"""
Relative Strength Analyzer - Individual Stock vs Sector/Industry

Provides comparative analysis between a stock and its sector:
- Price performance comparison
- Volume/turnover comparison  
- Identifies outperformers/underperformers
- Generates actionable insights
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SectorPerformance:
    """Sector/Industry performance data"""
    sector_name: str
    change_pct: float                    # 当日涨跌幅
    change_5d: float = 0.0               # 5日涨跌幅
    change_20d: float = 0.0              # 20日涨跌幅
    turnover_rate: float = 0.0           # 换手率
    up_count: int = 0                    # 上涨家数
    down_count: int = 0                  # 下跌家数
    limit_up_count: int = 0              # 涨停家数
    limit_down_count: int = 0            # 跌停家数
    leading_stock: str = ""              # 领涨股
    leading_stock_change: float = 0.0    # 领涨股涨幅


@dataclass
class RelativeStrengthResult:
    """Relative strength analysis result"""
    stock_code: str
    stock_name: str
    stock_change_pct: float              # 个股涨跌幅
    
    sector_name: str                     # 所属板块
    sector_change_pct: float             # 板块涨跌幅
    
    # Relative strength metrics
    relative_strength_1d: float = 0.0    # 相对强度（当日）
    relative_strength_5d: float = 0.0    # 相对强度（5日）
    relative_strength_20d: float = 0.0   # 相对强度（20日）
    
    # Classification
    performance_type: str = "neutral"    # outperform/underperform/neutral/contrarian
    performance_reason: str = ""         # 表现原因说明
    
    # Context
    sector_performance: Optional[SectorPerformance] = None
    
    # Action suggestion
    action_hint: str = ""                # 操作建议


class RelativeStrengthAnalyzer:
    """
    Relative Strength Analyzer
    
    Analyzes how a stock performs relative to its sector/industry.
    This is crucial for identifying:
    - Stocks that are "掉队" (lagging behind sector)
    - Stocks that are leading the sector
    - Contrarian opportunities
    """
    
    def __init__(self):
        self._akshare = None
        self._sector_cache = {}
        self._cache_time = None
    
    def _get_akshare(self):
        """Lazy import akshare"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare
    
    def get_stock_sector(self, stock_code: str) -> Optional[str]:
        """
        Get the sector/industry for a stock
        
        Uses akshare stock_individual_info_em API
        """
        ak = self._get_akshare()
        
        try:
            info_df = ak.stock_individual_info_em(symbol=stock_code)
            if info_df is not None and not info_df.empty:
                industry_row = info_df[info_df['item'] == '行业']
                if not industry_row.empty:
                    return str(industry_row.iloc[0]['value'])
                
                # Try sector field
                sector_row = info_df[info_df['item'] == '板块']
                if not sector_row.empty:
                    return str(sector_row.iloc[0]['value'])
        except Exception as e:
            logger.debug(f"[相对强度] 获取 {stock_code} 行业信息失败: {e}")
        
        return None
    
    def get_sector_performance(self, sector_name: str) -> Optional[SectorPerformance]:
        """
        Get performance data for a sector
        
        Uses akshare stock_board_industry_name_em API
        """
        ak = self._get_akshare()
        
        try:
            # Get industry board data
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return None
            
            # Find the sector
            sector_row = df[df['板块名称'] == sector_name]
            if sector_row.empty:
                # Try partial match
                for idx, row in df.iterrows():
                    if sector_name in str(row['板块名称']) or str(row['板块名称']) in sector_name:
                        sector_row = df.iloc[[idx]]
                        break
            
            if sector_row.empty:
                logger.debug(f"[相对强度] 未找到板块 {sector_name}")
                return None
            
            row = sector_row.iloc[0]
            
            # Get sector constituents for additional metrics
            try:
                cons_df = ak.stock_board_industry_cons_em(symbol=sector_name)
                up_count = 0
                down_count = 0
                limit_up = 0
                limit_down = 0
                leading_stock = ""
                leading_change = 0.0
                
                if cons_df is not None and not cons_df.empty:
                    for _, stock_row in cons_df.iterrows():
                        change = float(stock_row.get('涨跌幅', 0))
                        if change > 0:
                            up_count += 1
                        elif change < 0:
                            down_count += 1
                        
                        if change >= 9.9:
                            limit_up += 1
                        elif change <= -9.9:
                            limit_down += 1
                        
                        if change > leading_change:
                            leading_change = change
                            leading_stock = str(stock_row.get('股票名称', ''))
                
                return SectorPerformance(
                    sector_name=sector_name,
                    change_pct=float(row.get('涨跌幅', 0)),
                    turnover_rate=float(row.get('换手率', 0)) if '换手率' in row else 0.0,
                    up_count=up_count,
                    down_count=down_count,
                    limit_up_count=limit_up,
                    limit_down_count=limit_down,
                    leading_stock=leading_stock,
                    leading_stock_change=leading_change,
                )
            except Exception as e:
                logger.debug(f"[相对强度] 获取板块成分股失败: {e}")
                return SectorPerformance(
                    sector_name=sector_name,
                    change_pct=float(row.get('涨跌幅', 0)),
                )
                
        except Exception as e:
            logger.error(f"[相对强度] 获取板块 {sector_name} 数据失败: {e}")
            return None
    
    def get_stock_historical_change(self, stock_code: str, days: int) -> Optional[float]:
        """
        Get stock change over N days
        
        Returns cumulative change percentage
        """
        ak = self._get_akshare()
        
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days + 10)).strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            if df is None or len(df) < 2:
                return None
            
            # Get the change over the period
            if len(df) >= days:
                recent = df.tail(days)
                start_price = recent.iloc[0]['收盘']
                end_price = recent.iloc[-1]['收盘']
                return (end_price - start_price) / start_price * 100
            
            return None
            
        except Exception as e:
            logger.debug(f"[相对强度] 获取 {stock_code} 历史涨跌失败: {e}")
            return None
    
    def analyze(self, stock_code: str, stock_name: str = "", stock_change: float = 0.0) -> Optional[RelativeStrengthResult]:
        """
        Analyze relative strength of a stock vs its sector
        
        Args:
            stock_code: Stock code
            stock_name: Stock name (optional, will fetch if not provided)
            stock_change: Today's change percentage (optional, will fetch if not provided)
            
        Returns:
            RelativeStrengthResult or None if sector info unavailable
        """
        # Get stock sector
        sector_name = self.get_stock_sector(stock_code)
        if not sector_name:
            logger.warning(f"[相对强度] 无法获取 {stock_code} 的行业信息")
            return None
        
        # Get sector performance
        sector_perf = self.get_sector_performance(sector_name)
        if not sector_perf:
            logger.warning(f"[相对强度] 无法获取板块 {sector_name} 的数据")
            return None
        
        # Fetch stock data if not provided
        if not stock_name or stock_change == 0.0:
            try:
                ak = self._get_akshare()
                quote = self._get_realtime_quote(stock_code)
                if quote:
                    stock_name = stock_name or quote.get('name', '')
                    stock_change = stock_change or quote.get('change_pct', 0.0)
            except Exception as e:
                logger.debug(f"[相对强度] 获取实时行情失败: {e}")
        
        # Calculate relative strength
        rs_1d = stock_change - sector_perf.change_pct
        
        # Get historical relative strength
        stock_5d = self.get_stock_historical_change(stock_code, 5)
        stock_20d = self.get_stock_historical_change(stock_code, 20)
        
        # Estimate sector historical changes (simplified)
        # In production, should calculate from sector index data
        sector_5d = sector_perf.change_pct * 5 * 0.6  # Rough estimate
        sector_20d = sector_perf.change_pct * 20 * 0.4
        
        rs_5d = (stock_5d - sector_5d) if stock_5d else 0.0
        rs_20d = (stock_20d - sector_20d) if stock_20d else 0.0
        
        # Determine performance type
        perf_type, perf_reason = self._classify_performance(
            stock_change=stock_change,
            sector_change=sector_perf.change_pct,
            rs_1d=rs_1d,
            rs_5d=rs_5d,
            sector_perf=sector_perf,
        )
        
        # Generate action hint
        action_hint = self._generate_action_hint(
            perf_type=perf_type,
            stock_change=stock_change,
            sector_change=sector_perf.change_pct,
            sector_perf=sector_perf,
        )
        
        return RelativeStrengthResult(
            stock_code=stock_code,
            stock_name=stock_name,
            stock_change_pct=stock_change,
            sector_name=sector_name,
            sector_change_pct=sector_perf.change_pct,
            relative_strength_1d=rs_1d,
            relative_strength_5d=rs_5d,
            relative_strength_20d=rs_20d,
            performance_type=perf_type,
            performance_reason=perf_reason,
            sector_performance=sector_perf,
            action_hint=action_hint,
        )
    
    def _get_realtime_quote(self, stock_code: str) -> Optional[Dict]:
        """Get realtime quote using akshare"""
        ak = self._get_akshare()
        
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                row = df[df['代码'] == stock_code]
                if not row.empty:
                    row = row.iloc[0]
                    return {
                        'name': str(row.get('名称', '')),
                        'change_pct': float(row.get('涨跌幅', 0)),
                    }
        except Exception as e:
            logger.debug(f"[相对强度] 获取实时行情失败: {e}")
        
        return None
    
    def _classify_performance(
        self,
        stock_change: float,
        sector_change: float,
        rs_1d: float,
        rs_5d: float,
        sector_perf: SectorPerformance,
    ) -> Tuple[str, str]:
        """
        Classify stock performance relative to sector
        
        Returns:
            (performance_type, reason)
        """
        # Strong outperformer: stock up significantly more than sector
        if stock_change > 3 and rs_1d > 2:
            return "strong_outperform", f"强势领涨，跑赢板块{rs_1d:.1f}个百分点"
        
        # Outperformer: stock up more than sector
        if stock_change > 0 and sector_change > 0 and rs_1d > 1:
            return "outperform", f"跑赢板块{rs_1d:.1f}个百分点，跟随板块上涨"
        
        # Underperformer: stock down more than sector
        if stock_change < sector_change and stock_change < 0:
            gap = abs(rs_1d)
            if sector_change > 0:
                return "weak_underperform", f"板块上涨{sector_change:.1f}%但个股下跌，掉队明显"
            else:
                return "underperform", f"跌幅大于板块{gap:.1f}个百分点，破位补跌性质"
        
        # Contrarian: sector up but stock down (or vice versa)
        if sector_change > 1 and stock_change < -2:
            return "contrarian_weak", f"板块上涨{sector_change:.1f}%但个股下跌{abs(stock_change):.1f}%，严重背离"
        
        if sector_change < -1 and stock_change > 2:
            return "contrarian_strong", f"板块下跌但个股逆势上涨，有独立行情"
        
        # Neutral: similar performance
        if abs(rs_1d) <= 1:
            return "neutral", f"与板块同步，涨跌幅差值{rs_1d:.1f}%"
        
        # Default
        if rs_1d > 0:
            return "slight_outperform", f"小幅跑赢板块{rs_1d:.1f}个百分点"
        else:
            return "slight_underperform", f"小幅跑输板块{abs(rs_1d):.1f}个百分点"
    
    def _generate_action_hint(
        self,
        perf_type: str,
        stock_change: float,
        sector_change: float,
        sector_perf: SectorPerformance,
    ) -> str:
        """
        Generate actionable trading hint
        
        Based on relative strength analysis
        """
        hints = []
        
        if perf_type == "strong_outperform":
            hints.append("个股表现强势，可作为板块龙头关注")
            if sector_perf.limit_up_count >= 3:
                hints.append(f"板块内{sector_perf.limit_up_count}只涨停，赚钱效应好")
        
        elif perf_type == "outperform":
            hints.append("个股跑赢板块，可继续持有观察")
        
        elif perf_type == "weak_underperform":
            hints.append("⚠️ 个股严重掉队，建议审视持仓理由")
            hints.append("如无特殊利好，考虑换股至板块龙头")
        
        elif perf_type == "underperform":
            hints.append("个股破位补跌，谨慎抄底")
            hints.append("建议等待企稳信号再考虑介入")
        
        elif perf_type == "contrarian_weak":
            hints.append("⚠️ 个股与板块严重背离")
            hints.append("可能有基本面问题，建议查看公司公告")
        
        elif perf_type == "contrarian_strong":
            hints.append("个股逆势走强，可能有独立催化剂")
            hints.append("关注是否有利好消息或主力资金介入")
        
        elif perf_type == "neutral":
            hints.append("个股与板块同步，无特殊操作建议")
        
        else:
            if stock_change > 0:
                hints.append("跟随板块上涨，可继续持有")
            else:
                hints.append("跟随板块回调，关注支撑位")
        
        return " | ".join(hints)
    
    def generate_report(self, result: RelativeStrengthResult) -> List[str]:
        """
        Generate markdown report for relative strength analysis
        
        Args:
            result: RelativeStrengthResult object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"### 📊 相对强度分析 ({result.stock_name} vs {result.sector_name})",
            "",
        ]
        
        # Performance comparison table
        lines.append("| 指标 | 个股 | 板块 | 差值 |")
        lines.append("|------|------|------|------|")
        lines.append(f"| 当日涨跌 | {result.stock_change_pct:+.2f}% | {result.sector_change_pct:+.2f}% | {result.relative_strength_1d:+.2f}% |")
        
        if result.relative_strength_5d != 0:
            lines.append(f"| 5日涨跌 | - | - | {result.relative_strength_5d:+.2f}% |")
        
        lines.append("")
        
        # Performance type with emoji
        perf_emoji = {
            "strong_outperform": "🟢🟢",
            "outperform": "🟢",
            "slight_outperform": "🟡",
            "neutral": "⚪",
            "slight_underperform": "🟠",
            "underperform": "🔴",
            "weak_underperform": "🔴🔴",
            "contrarian_weak": "⚠️",
            "contrarian_strong": "💎",
        }
        
        emoji = perf_emoji.get(result.performance_type, "⚪")
        lines.append(f"**表现类型**: {emoji} {result.performance_type}")
        lines.append(f"**分析结论**: {result.performance_reason}")
        lines.append("")
        
        # Sector context
        if result.sector_performance:
            sp = result.sector_performance
            lines.append("#### 📈 板块概况")
            lines.append("")
            lines.append(f"> {sp.sector_name}: 涨跌{sp.change_pct:+.2f}% | 上涨{sp.up_count}家 | 下跌{sp.down_count}家 | 涨停{sp.limit_up_count}只")
            if sp.leading_stock:
                lines.append(f"> 领涨股: {sp.leading_stock} ({sp.leading_stock_change:+.2f}%)")
            lines.append("")
        
        # Action hint
        lines.append("#### 💡 操作建议")
        lines.append("")
        lines.append(result.action_hint)
        lines.append("")
        
        return lines


# Singleton
_analyzer_instance: Optional[RelativeStrengthAnalyzer] = None


def get_relative_strength_analyzer() -> RelativeStrengthAnalyzer:
    """Get RelativeStrengthAnalyzer singleton"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = RelativeStrengthAnalyzer()
    return _analyzer_instance