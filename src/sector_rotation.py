# -*- coding: utf-8 -*-
"""
Sector Rotation Map (主线轮动图谱)

Identifies and tracks market hot sectors and their lifecycle:
- Top active sectors identification
- Sector lifecycle stage (萌芽、发酵、高潮、衰退)
- Capital flow tracking between sectors
- Rotation predictions
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SectorStage(Enum):
    """Sector lifecycle stages"""
    BUDDING = "budding"           # 萌芽期：资金开始流入，涨幅不大
    FERMENTING = "fermenting"     # 发酵期：关注度提升，龙头确立
    CLIMAX = "climax"             # 高潮期：全面爆发，涨幅较大
    DECLINING = "declining"       # 衰退期：龙头分歧，资金流出


class SectorStrength(Enum):
    """Sector strength rating"""
    VERY_STRONG = "very_strong"   # 非常强势
    STRONG = "strong"             # 强势
    MODERATE = "moderate"         # 中等
    WEAK = "weak"                 # 弱势
    VERY_WEAK = "very_weak"       # 非常弱势


@dataclass
class SectorInfo:
    """Sector/Industry information"""
    name: str
    change_pct: float = 0.0              # 当日涨跌幅
    change_5d: float = 0.0               # 5日涨跌幅
    turnover_rate: float = 0.0           # 换手率
    
    # Market stats
    up_count: int = 0                    # 上涨家数
    down_count: int = 0                  # 下跌家数
    limit_up_count: int = 0              # 涨停家数
    limit_down_count: int = 0            # 跌停家数
    
    # Capital flow
    net_inflow: float = 0.0              # 净流入（万）
    main_inflow: float = 0.0             # 主力净流入
    
    # Leading stocks
    leading_stock: str = ""              # 龙头股
    leading_change: float = 0.0          # 龙头涨幅
    dragon_2: str = ""                   # 龙二
    dragon_3: str = ""                   # 龙三


@dataclass
class HotSector:
    """A hot sector with detailed analysis"""
    sector: SectorInfo
    
    # Analysis results
    stage: SectorStage = SectorStage.FERMENTING
    strength: SectorStrength = SectorStrength.MODERATE
    score: float = 50.0                  # 综合得分 0-100
    
    # Trend
    trend: str = "neutral"               # accelerating/peaking/decelerating/neutral
    trend_description: str = ""
    
    # Capital flow
    capital_trend: str = "neutral"       # inflowing/outflowing/neutral
    
    # Trading hints
    action_hint: str = ""
    risk_level: str = "medium"           # low/medium/high


@dataclass
class SectorRotationResult:
    """Complete sector rotation analysis result"""
    analysis_date: str
    
    # Hot sectors (top 5)
    hot_sectors: List[HotSector] = field(default_factory=list)
    
    # Sector rotation summary
    rotation_summary: str = ""
    
    # Market theme
    main_theme: str = ""                 # 当前主线
    main_theme_description: str = ""
    
    # Recommendations
    top_picks: List[Dict[str, Any]] = field(default_factory=list)
    avoid_sectors: List[str] = field(default_factory=list)
    
    # Key signals
    signals: List[str] = field(default_factory=list)


class SectorRotationAnalyzer:
    """
    Sector Rotation Analyzer
    
    Identifies market hot sectors and their lifecycle stages.
    Helps traders:
    - Identify which sectors are leading the market
    - Understand sector rotation patterns
    - Make informed sector allocation decisions
    """
    
    # Sector stage thresholds
    LIMIT_UP_THRESHOLD_CLIMAX = 5        # 涨停>=5只视为高潮
    LIMIT_UP_THRESHOLD_STRONG = 3        # 涨停>=3只视为强势
    CHANGE_THRESHOLD_CLIMAX = 4.0        # 涨幅>=4%视为高潮
    CHANGE_THRESHOLD_STRONG = 2.5        # 涨幅>=2.5%视为强势
    
    def __init__(self):
        self._akshare = None
    
    def _get_akshare(self):
        """Lazy import akshare"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare
    
    def get_all_sectors_performance(self) -> List[SectorInfo]:
        """
        Get performance data for all sectors
        
        Uses akshare stock_board_industry_name_em API
        """
        ak = self._get_akshare()
        
        try:
            logger.info("[主线轮动] 获取板块行情数据...")
            
            # Get industry board data
            df = ak.stock_board_industry_name_em()
            
            if df is None or df.empty:
                return []
            
            sectors = []
            for _, row in df.iterrows():
                try:
                    sector = SectorInfo(
                        name=str(row.get('板块名称', '')),
                        change_pct=float(row.get('涨跌幅', 0)),
                        turnover_rate=float(row.get('换手率', 0)) if '换手率' in row else 0.0,
                    )
                    sectors.append(sector)
                except Exception as e:
                    logger.debug(f"[主线轮动] 解析板块数据失败: {e}")
                    continue
            
            logger.info(f"[主线轮动] 获取到 {len(sectors)} 个板块数据")
            return sectors
            
        except Exception as e:
            logger.error(f"[主线轮动] 获取板块数据失败: {e}")
            return []
    
    def get_sector_details(self, sector_name: str) -> Optional[SectorInfo]:
        """
        Get detailed information for a specific sector
        
        Args:
            sector_name: Name of the sector
            
        Returns:
            SectorInfo with detailed data
        """
        ak = self._get_akshare()
        
        try:
            # Get sector constituents
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            
            if df is None or df.empty:
                return None
            
            sector = SectorInfo(name=sector_name)
            
            up_count = 0
            down_count = 0
            limit_up = 0
            limit_down = 0
            leading_change = 0
            leading_stock = ""
            dragon_2_change = 0
            dragon_2 = ""
            
            # Sort by change to find leaders
            df_sorted = df.sort_values(by='涨跌幅', ascending=False)
            
            for idx, row in df_sorted.iterrows():
                change = float(row.get('涨跌幅', 0))
                
                if change > 0:
                    up_count += 1
                elif change < 0:
                    down_count += 1
                
                if change >= 9.9:
                    limit_up += 1
                elif change <= -9.9:
                    limit_down += 1
                
                # Find leading stocks
                if change > leading_change:
                    dragon_2_change = leading_change
                    dragon_2 = leading_stock
                    leading_change = change
                    leading_stock = str(row.get('股票名称', ''))
                elif change > dragon_2_change:
                    dragon_2_change = change
                    dragon_2 = str(row.get('股票名称', ''))
            
            sector.up_count = up_count
            sector.down_count = down_count
            sector.limit_up_count = limit_up
            sector.limit_down_count = limit_down
            sector.leading_stock = leading_stock
            sector.leading_change = leading_change
            sector.dragon_2 = dragon_2
            
            # Calculate average change
            sector.change_pct = df['涨跌幅'].astype(float).mean()
            
            return sector
            
        except Exception as e:
            logger.debug(f"[主线轮动] 获取板块 {sector_name} 详情失败: {e}")
            return None
    
    def identify_hot_sectors(self, sectors: List[SectorInfo], top_n: int = 5) -> List[HotSector]:
        """
        Identify hot sectors based on performance
        
        Args:
            sectors: List of all sectors
            top_n: Number of top sectors to return
            
        Returns:
            List of HotSector objects
        """
        # Sort by change percentage
        sorted_sectors = sorted(sectors, key=lambda x: x.change_pct, reverse=True)
        
        hot_sectors = []
        for sector in sorted_sectors[:top_n * 2]:  # Get more candidates for detailed analysis
            # Get detailed info
            detailed = self.get_sector_details(sector.name)
            if detailed:
                sector = detailed
            
            # Determine stage and strength
            hot_sector = HotSector(sector=sector)
            hot_sector.stage = self._determine_stage(sector)
            hot_sector.strength = self._determine_strength(sector)
            hot_sector.score = self._calculate_score(sector)
            hot_sector.trend = self._determine_trend(sector)
            hot_sector.trend_description = self._generate_trend_description(hot_sector)
            hot_sector.action_hint = self._generate_action_hint(hot_sector)
            hot_sector.risk_level = self._determine_risk_level(hot_sector)
            
            hot_sectors.append(hot_sector)
        
        # Sort by score and return top N
        hot_sectors.sort(key=lambda x: x.score, reverse=True)
        return hot_sectors[:top_n]
    
    def _determine_stage(self, sector: SectorInfo) -> SectorStage:
        """
        Determine sector lifecycle stage
        
        Logic:
        - Climax: High limit-up count, high gains, likely overheated
        - Fermenting: Moderate limit-up, gaining momentum
        - Budding: Low limit-up but positive, early stage
        - Declining: Negative or very low gains
        """
        if sector.limit_up_count >= self.LIMIT_UP_THRESHOLD_CLIMAX:
            return SectorStage.CLIMAX
        elif sector.limit_up_count >= self.LIMIT_UP_THRESHOLD_STRONG:
            if sector.change_pct >= self.CHANGE_THRESHOLD_CLIMAX:
                return SectorStage.CLIMAX
            else:
                return SectorStage.FERMENTING
        elif sector.change_pct >= self.CHANGE_THRESHOLD_STRONG:
            return SectorStage.FERMENTING
        elif sector.change_pct > 0:
            return SectorStage.BUDDING
        else:
            return SectorStage.DECLINING
    
    def _determine_strength(self, sector: SectorInfo) -> SectorStrength:
        """Determine sector strength rating"""
        if sector.limit_up_count >= 5 or sector.change_pct >= 4:
            return SectorStrength.VERY_STRONG
        elif sector.limit_up_count >= 3 or sector.change_pct >= 2.5:
            return SectorStrength.STRONG
        elif sector.change_pct >= 1:
            return SectorStrength.MODERATE
        elif sector.change_pct > 0:
            return SectorStrength.WEAK
        else:
            return SectorStrength.VERY_WEAK
    
    def _calculate_score(self, sector: SectorInfo) -> float:
        """Calculate composite score for a sector (0-100)"""
        score = 50.0  # Base score
        
        # Change contribution (max +20)
        score += min(20, sector.change_pct * 5)
        
        # Limit-up contribution (max +20)
        score += min(20, sector.limit_up_count * 4)
        
        # Up/Down ratio contribution (max +10)
        total = sector.up_count + sector.down_count
        if total > 0:
            ratio = sector.up_count / total
            score += (ratio - 0.5) * 20
        
        return max(0, min(100, score))
    
    def _determine_trend(self, sector: SectorInfo) -> str:
        """Determine sector trend direction"""
        if sector.change_pct >= 3 and sector.limit_up_count >= 3:
            return "accelerating"
        elif sector.change_pct >= 4 and sector.limit_up_count >= 5:
            return "peaking"
        elif sector.change_pct < 0:
            return "decelerating"
        else:
            return "neutral"
    
    def _generate_trend_description(self, hot_sector: HotSector) -> str:
        """Generate human-readable trend description"""
        sector = hot_sector.sector
        stage = hot_sector.stage
        
        if stage == SectorStage.CLIMAX:
            return f"板块处于高潮期，涨停{sector.limit_up_count}只，注意分化风险"
        elif stage == SectorStage.FERMENTING:
            return f"板块发酵中，龙头{sector.leading_stock}涨幅{sector.leading_change:.1f}%，可跟踪"
        elif stage == SectorStage.BUDDING:
            return f"板块萌芽期，资金开始关注，可低吸布局"
        else:
            return f"板块调整中，等待企稳信号"
    
    def _generate_action_hint(self, hot_sector: HotSector) -> str:
        """Generate action hint for a sector"""
        stage = hot_sector.stage
        strength = hot_sector.strength
        
        if stage == SectorStage.CLIMAX:
            return "⚠️ 板块高潮，龙头分歧加大，谨慎追高，关注低位补涨"
        elif stage == SectorStage.FERMENTING:
            if strength in [SectorStrength.VERY_STRONG, SectorStrength.STRONG]:
                return "✅ 板块强势发酵，可跟随龙头，注意去弱留强"
            else:
                return "👁️ 板块发酵中，可关注龙头股表现"
        elif stage == SectorStage.BUDDING:
            return "🌱 板块萌芽，可低吸布局龙头，设好止损"
        else:
            return "⏸️ 板块调整，暂观望，等待企稳信号"
    
    def _determine_risk_level(self, hot_sector: HotSector) -> str:
        """Determine risk level for a sector"""
        if hot_sector.stage == SectorStage.CLIMAX:
            return "high"
        elif hot_sector.stage == SectorStage.DECLINING:
            return "high"
        elif hot_sector.strength in [SectorStrength.VERY_STRONG, SectorStrength.STRONG]:
            return "medium"
        else:
            return "low"
    
    def analyze(self) -> SectorRotationResult:
        """
        Perform complete sector rotation analysis
        
        Returns:
            SectorRotationResult with all analysis
        """
        result = SectorRotationResult(
            analysis_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        # Get all sectors
        sectors = self.get_all_sectors_performance()
        
        if not sectors:
            logger.warning("[主线轮动] 无板块数据，返回空结果")
            result.rotation_summary = "无法获取板块数据"
            return result
        
        # Identify hot sectors
        result.hot_sectors = self.identify_hot_sectors(sectors)
        
        # Generate summary
        if result.hot_sectors:
            top = result.hot_sectors[0]
            result.main_theme = top.sector.name
            result.main_theme_description = top.trend_description
        
        # Generate rotation summary
        result.rotation_summary = self._generate_rotation_summary(result.hot_sectors)
        
        # Generate top picks
        result.top_picks = self._generate_top_picks(result.hot_sectors)
        
        # Identify sectors to avoid
        result.avoid_sectors = self._identify_avoid_sectors(sectors)
        
        # Generate signals
        result.signals = self._generate_signals(result.hot_sectors)
        
        logger.info(f"[主线轮动] 主线板块: {result.main_theme}, "
                   f"强势板块数: {len([s for s in result.hot_sectors if s.strength.value in ['very_strong', 'strong']])}")
        
        return result
    
    def _generate_rotation_summary(self, hot_sectors: List[HotSector]) -> str:
        """Generate sector rotation summary"""
        if not hot_sectors:
            return "暂无热点板块"
        
        # Categorize by stage
        climax = [s for s in hot_sectors if s.stage == SectorStage.CLIMAX]
        fermenting = [s for s in hot_sectors if s.stage == SectorStage.FERMENTING]
        budding = [s for s in hot_sectors if s.stage == SectorStage.BUDDING]
        
        parts = []
        
        if climax:
            parts.append(f"高潮期: {', '.join([s.sector.name for s in climax])}")
        if fermenting:
            parts.append(f"发酵期: {', '.join([s.sector.name for s in fermenting])}")
        if budding:
            parts.append(f"萌芽期: {', '.join([s.sector.name for s in budding])}")
        
        return " | ".join(parts) if parts else "板块轮动不明显"
    
    def _generate_top_picks(self, hot_sectors: List[HotSector]) -> List[Dict[str, Any]]:
        """Generate top stock picks from hot sectors"""
        picks = []
        
        for hot in hot_sectors[:3]:
            sector = hot.sector
            
            if sector.leading_stock:
                picks.append({
                    'stock': sector.leading_stock,
                    'sector': sector.name,
                    'change': sector.leading_change,
                    'reason': f"{sector.name}龙头",
                    'stage': hot.stage.value,
                    'action': hot.action_hint,
                })
            
            if sector.dragon_2:
                picks.append({
                    'stock': sector.dragon_2,
                    'sector': sector.name,
                    'change': 0,  # Would need to fetch
                    'reason': f"{sector.name}龙二",
                    'stage': hot.stage.value,
                    'action': "跟随龙头走势",
                })
        
        return picks
    
    def _identify_avoid_sectors(self, sectors: List[SectorInfo]) -> List[str]:
        """Identify sectors to avoid"""
        avoid = []
        
        # Sort by change (ascending)
        sorted_sectors = sorted(sectors, key=lambda x: x.change_pct)
        
        for sector in sorted_sectors[:3]:
            if sector.change_pct < -1:
                avoid.append(f"{sector.name} ({sector.change_pct:+.1f}%)")
        
        return avoid
    
    def _generate_signals(self, hot_sectors: List[HotSector]) -> List[str]:
        """Generate trading signals from analysis"""
        signals = []
        
        for hot in hot_sectors:
            sector = hot.sector
            
            # High limit-up count signal
            if sector.limit_up_count >= 5:
                signals.append(f"🔥 {sector.name}涨停{sector.limit_up_count}只，板块爆发")
            
            # Climax stage warning
            if hot.stage == SectorStage.CLIMAX:
                signals.append(f"⚠️ {sector.name}进入高潮期，注意分化风险")
            
            # Budding opportunity
            if hot.stage == SectorStage.BUDDING and hot.strength == SectorStrength.MODERATE:
                signals.append(f"🌱 {sector.name}萌芽期，可低吸布局")
            
            # Strong leading stock
            if sector.leading_change >= 7:
                signals.append(f"⭐ {sector.name}龙头{sector.leading_stock}涨幅{sector.leading_change:.0f}%")
        
        return signals
    
    def generate_report(self, result: SectorRotationResult) -> List[str]:
        """
        Generate markdown report for sector rotation
        
        Args:
            result: SectorRotationResult object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"## 🔄 主线轮动图谱 ({result.analysis_date})",
            "",
        ]
        
        # Main theme
        if result.main_theme:
            lines.append(f"### 📍 当日主线: {result.main_theme}")
            lines.append("")
            lines.append(f"> {result.main_theme_description}")
            lines.append("")
        
        # Rotation summary
        lines.append(f"**板块轮动**: {result.rotation_summary}")
        lines.append("")
        
        # Hot sectors table
        if result.hot_sectors:
            lines.append("#### 🔥 热门板块排行")
            lines.append("")
            lines.append("| 排名 | 板块 | 涨幅 | 涨停数 | 阶段 | 强度 | 操作建议 |")
            lines.append("|------|------|------|--------|------|------|----------|")
            
            stage_names = {
                SectorStage.CLIMAX: "🔴高潮",
                SectorStage.FERMENTING: "🟡发酵",
                SectorStage.BUDDING: "🟢萌芽",
                SectorStage.DECLINING: "⚫衰退",
            }
            
            strength_names = {
                SectorStrength.VERY_STRONG: "★★★★★",
                SectorStrength.STRONG: "★★★★",
                SectorStrength.MODERATE: "★★★",
                SectorStrength.WEAK: "★★",
                SectorStrength.VERY_WEAK: "★",
            }
            
            for idx, hot in enumerate(result.hot_sectors, 1):
                sector = hot.sector
                stage_name = stage_names.get(hot.stage, "未知")
                strength_name = strength_names.get(hot.strength, "★")
                
                lines.append(f"| {idx} | {sector.name} | {sector.change_pct:+.2f}% | "
                           f"{sector.limit_up_count} | {stage_name} | {strength_name} | "
                           f"{hot.action_hint[:15]}... |")
            
            lines.append("")
        
        # Top picks
        if result.top_picks:
            lines.append("#### 🎯 龙头股关注")
            lines.append("")
            
            for pick in result.top_picks[:5]:
                lines.append(f"- **{pick['stock']}** ({pick['sector']}): {pick['reason']}")
            
            lines.append("")
        
        # Avoid list
        if result.avoid_sectors:
            lines.append("#### ⛔ 回避板块")
            lines.append("")
            for avoid in result.avoid_sectors:
                lines.append(f"- {avoid}")
            lines.append("")
        
        # Signals
        if result.signals:
            lines.append("#### 📢 信号提示")
            lines.append("")
            for signal in result.signals:
                lines.append(f"- {signal}")
            lines.append("")
        
        return lines


# Singleton
_analyzer_instance: Optional[SectorRotationAnalyzer] = None


def get_sector_rotation_analyzer() -> SectorRotationAnalyzer:
    """Get SectorRotationAnalyzer singleton"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SectorRotationAnalyzer()
    return _analyzer_instance