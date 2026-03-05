# -*- coding: utf-8 -*-
"""
Dragon-Tiger List (龙虎榜) Seat Analyzer

Provides advanced analysis of LHB trading seats including:
- Seat type classification (institution/hot money/northbound)
- Known hot money seat identification
- Seat statistics and patterns
- Sector concentration analysis
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


# === Known Hot Money Seats Database ===
# Data sources: public reports, forums, professional analysis
# Format: seat_name -> (alias, style, reputation)

KNOWN_HOT_MONEY_SEATS = {
    # ========== 知名游资席位 ==========
    # 华鑫系 (散户集中营)
    "华鑫证券有限责任公司上海分公司": ("华鑫上海", "散户集中营", "neutral"),
    "华鑫证券有限责任公司上海浦东新区东方路证券营业部": ("华鑫东方路", "跟风盘", "neutral"),
    
    # 拉萨系 (西藏东方财富证券，散户大本营)
    "西藏东方财富证券股份有限公司拉萨团结路第一证券营业部": ("拉萨团结路1", "散户大本营", "neutral"),
    "西藏东方财富证券股份有限公司拉萨团结路第二证券营业部": ("拉萨团结路2", "散户大本营", "neutral"),
    "西藏东方财富证券股份有限公司拉萨东环路第一证券营业部": ("拉萨东环路1", "散户大本营", "neutral"),
    "西藏东方财富证券股份有限公司拉萨东环路第二证券营业部": ("拉萨东环路2", "散户大本营", "neutral"),
    
    # 呼家楼系 (知名游资，擅长连板)
    "中信证券股份有限公司西安朱雀大街证券营业部": ("呼家楼", "连板高手", "bullish"),
    "中信证券股份有限公司西安朱雀大街证券营业部": ("朱雀大街", "趋势游资", "bullish"),
    
    # 深股通/沪股通专用
    "沪股通专用": ("沪股通", "北向资金", "institution"),
    "深股通专用": ("深股通", "北向资金", "institution"),
    
    # 机构专用
    "机构专用": ("机构", "机构资金", "institution"),
    
    # 知名游资
    "国泰君安证券股份有限公司上海分公司": ("国君上海", "量化游资", "neutral"),
    "国泰君安证券股份有限公司上海江苏路证券营业部": ("国君江苏路", "老牌游资", "bullish"),
    "中信证券股份有限公司上海溧阳路证券营业部": ("溧阳路", "游资大佬", "bullish"),
    "银河证券股份有限公司绍兴证券营业部": ("银河绍兴", "赵老哥席位", "bullish"),
    "银河证券股份有限公司杭州新塘路证券营业部": ("银河新塘路", "游资", "neutral"),
    "华泰证券股份有限公司深圳益田路荣超商务中心证券营业部": ("华泰荣超", "打板高手", "bullish"),
    "华泰证券股份有限公司南京中华路证券营业部": ("华泰中华路", "短线游资", "neutral"),
    "招商证券股份有限公司深圳蛇口工业七路证券营业部": ("招商蛇口", "游资", "neutral"),
    "中泰证券股份有限公司上海建国中路证券营业部": ("中泰建国中路", "游资", "neutral"),
    "财通证券股份有限公司杭州体育馆证券营业部": ("财通体育馆", "游资", "neutral"),
    "浙商证券股份有限公司绍兴分公司": ("浙商绍兴", "游资", "neutral"),
    "申万宏源证券有限公司上海闵行区东川路证券营业部": ("申万东川路", "游资", "neutral"),
    
    # 宁波解放南系 (涨停板敢死队)
    "光大证券股份有限公司宁波解放南路证券营业部": ("宁波解放南", "涨停敢死队", "aggressive"),
    "银河证券股份有限公司宁波解放南路证券营业部": ("银河解放南", "涨停敢死队", "aggressive"),
    
    # 其他知名席位
    "中国中金财富证券有限公司北京宋庄路证券营业部": ("中金宋庄路", "游资", "neutral"),
    "中信建投证券股份有限公司杭州庆春路证券营业部": ("中信庆春路", "游资", "neutral"),
    "华鑫证券有限责任公司杭州飞云江路证券营业部": ("华鑫飞云江", "游资", "neutral"),
    "东兴证券股份有限公司泉州温陵北路证券营业部": ("东兴温陵路", "游资", "neutral"),
    "华鑫证券有限责任公司宁波分公司": ("华鑫宁波", "游资", "neutral"),
    "财信证券有限责任公司杭州体育场路证券营业部": ("财信体育场路", "游资", "neutral"),
}

# Seat type classification rules
SEAT_TYPE_RULES = {
    "institution": ["机构专用", "机构"],
    "northbound": ["沪股通", "深股通", "股通专用"],
    "hot_money": ["证券营业部", "证券分公司", "证券有限公司"],
}


@dataclass
class SeatDetail:
    """Individual seat trading detail"""
    seat_name: str                        # 席位名称
    seat_type: str                        # 席位类型: institution/hot_money/northbound/unknown
    buy_amount: Optional[float] = None   # 买入金额（万元）
    sell_amount: Optional[float] = None  # 卖出金额（万元）
    net_amount: Optional[float] = None   # 净买入（万元）
    alias: Optional[str] = None          # 知名席位别名
    style: Optional[str] = None          # 操作风格
    reputation: Optional[str] = None     # 声誉评级: bullish/neutral/aggressive/institution
    

@dataclass
class LHBSeatAnalysis:
    """LHB seat analysis result for a single stock"""
    code: str
    name: str
    analysis_date: str
    close_price: float
    change_pct: float
    
    # Seat details
    buy_seats: List[SeatDetail] = field(default_factory=list)   # 买方前5席位
    sell_seats: List[SeatDetail] = field(default_factory=list)  # 卖方前5席位
    
    # Aggregated metrics
    institution_net_buy: float = 0.0       # 机构净买入（万元）
    hot_money_net_buy: float = 0.0         # 游资净买入（万元）
    northbound_net_buy: float = 0.0        # 北向资金净买入（万元）
    total_net_buy: float = 0.0             # 总净买入（万元）
    
    # Key findings
    has_institution_buy: bool = False      # 是否有机构买入
    has_hot_money_buy: bool = False        # 是否有知名游资买入
    has_northbound_buy: bool = False       # 是否有北向资金买入
    known_seats: List[str] = field(default_factory=list)  # 知名席位列表
    
    # Signal
    seat_signal: str = "neutral"           # 席位信号: bullish/bearish/neutral
    signal_reason: str = ""                # 信号原因


@dataclass
class SectorConcentration:
    """Sector concentration analysis for LHB stocks"""
    sector_name: str
    stock_count: int                      # 该板块上榜股票数
    total_net_buy: float                  # 板块总净买入（万元）
    stock_codes: List[str] = field(default_factory=list)
    stock_names: List[str] = field(default_factory=list)


class LHBSeatAnalyzer:
    """
    LHB Seat Analyzer
    
    Features:
    1. Fetch LHB seat details via akshare
    2. Classify seat types (institution/hot money/northbound)
    3. Identify known hot money seats
    4. Analyze sector concentration
    5. Generate trading signals based on seat activity
    """
    
    def __init__(self):
        self._akshare = None
        self._cache = {}  # Cache for daily data
        self._cache_date = None
    
    def _get_akshare(self):
        """Lazy import akshare"""
        if self._akshare is None:
            try:
                import akshare as ak
                self._akshare = ak
            except ImportError:
                logger.error("akshare not installed. Run: pip install akshare --upgrade")
                raise
        return self._akshare
    
    def _classify_seat_type(self, seat_name: str) -> str:
        """
        Classify seat type based on name patterns
        
        Returns:
            'institution' / 'northbound' / 'hot_money' / 'unknown'
        """
        for seat_type, patterns in SEAT_TYPE_RULES.items():
            for pattern in patterns:
                if pattern in seat_name:
                    return seat_type
        return "unknown"
    
    def _get_known_seat_info(self, seat_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get known seat info from database
        
        Returns:
            (alias, style, reputation) or (None, None, None)
        """
        # Exact match
        if seat_name in KNOWN_HOT_MONEY_SEATS:
            return KNOWN_HOT_MONEY_SEATS[seat_name]
        
        # Partial match for similar names
        for known_name, info in KNOWN_HOT_MONEY_SEATS.items():
            # Check if key parts match
            if len(seat_name) > 10 and len(known_name) > 10:
                if seat_name[:10] == known_name[:10]:
                    return info
        
        return None, None, None
    
    def _parse_seat_detail(self, seat_name: str, buy_amount: float = 0, sell_amount: float = 0) -> SeatDetail:
        """
        Parse seat detail with classification
        """
        seat_type = self._classify_seat_type(seat_name)
        alias, style, reputation = self._get_known_seat_info(seat_name)
        
        net_amount = buy_amount - sell_amount
        
        return SeatDetail(
            seat_name=seat_name,
            seat_type=seat_type,
            buy_amount=buy_amount if buy_amount else None,
            sell_amount=sell_amount if sell_amount else None,
            net_amount=net_amount if net_amount != 0 else None,
            alias=alias,
            style=style,
            reputation=reputation,
        )
    
    def get_lhb_stock_seats(self, code: str, days: int = 1) -> Optional[LHBSeatAnalysis]:
        """
        Get detailed seat analysis for a specific stock
        
        Uses ak.stock_lhb_stock_detail_em() to get seat-level data
        
        Args:
            code: Stock code
            days: Number of recent days to analyze
            
        Returns:
            LHBSeatAnalysis object or None
        """
        ak = self._get_akshare()
        
        try:
            # Get LHB detail for the stock
            # ak.stock_lhb_stock_detail_em returns trading seats for a specific stock
            today = datetime.now()
            
            for i in range(days):
                check_date = today - timedelta(days=i)
                date_str = check_date.strftime('%Y%m%d')
                
                try:
                    # Try to get stock-specific LHB detail
                    # Note: This API may need adjustment based on akshare version
                    logger.info(f"[LHB席位] 查询 {code} 在 {date_str} 的龙虎榜席位...")
                    
                    # Use the general LHB detail API
                    df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
                    
                    if df is None or df.empty:
                        continue
                    
                    # Filter for the specific stock
                    stock_df = df[df['代码'] == code]
                    if stock_df.empty:
                        continue
                    
                    # Get basic info from first row
                    first_row = stock_df.iloc[0]
                    
                    analysis = LHBSeatAnalysis(
                        code=code,
                        name=str(first_row.get('名称', '')),
                        analysis_date=date_str,
                        close_price=float(first_row.get('收盘价', 0)),
                        change_pct=float(first_row.get('涨跌幅', 0)),
                    )
                    
                    # Try to get seat-level details
                    # Note: akshare's stock_lhb_detail_em provides summary data
                    # For detailed seats, we need to use stock_lhb_stock_detail_em
                    try:
                        # Attempt to get seat details
                        seat_df = ak.stock_lhb_stock_detail_em(
                            symbol=code,
                            start_date=date_str,
                            end_date=date_str
                        )
                        
                        if seat_df is not None and not seat_df.empty:
                            analysis = self._parse_seat_df(analysis, seat_df)
                    except Exception as e:
                        logger.debug(f"[LHB席位] 无详细席位数据: {e}")
                        # Fallback: estimate from summary data
                        analysis = self._estimate_from_summary(analysis, stock_df)
                    
                    return analysis
                    
                except Exception as e:
                    logger.debug(f"[LHB席位] 查询 {date_str} 失败: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"[LHB席位] 获取 {code} 席位分析失败: {e}")
            return None
    
    def _parse_seat_df(self, analysis: LHBSeatAnalysis, seat_df) -> LHBSeatAnalysis:
        """Parse seat detail DataFrame"""
        try:
            # Separate buy and sell seats
            buy_seats = []
            sell_seats = []
            
            for _, row in seat_df.iterrows():
                direction = str(row.get('方向', '')).lower()
                seat_name = str(row.get('营业部名称', row.get('席位名称', '')))
                amount = float(row.get('买入金额', row.get('成交金额', 0))) / 10000  # Convert to 万元
                
                seat_detail = self._parse_seat_detail(
                    seat_name=seat_name,
                    buy_amount=amount if '买' in direction else 0,
                    sell_amount=amount if '卖' in direction else 0,
                )
                
                if '买' in direction:
                    buy_seats.append(seat_detail)
                else:
                    sell_seats.append(seat_detail)
            
            analysis.buy_seats = buy_seats[:5]  # Top 5 buy seats
            analysis.sell_seats = sell_seats[:5]  # Top 5 sell seats
            
            # Calculate aggregated metrics
            self._calculate_metrics(analysis)
            
            return analysis
            
        except Exception as e:
            logger.warning(f"[LHB席位] 解析席位数据失败: {e}")
            return analysis
    
    def _estimate_from_summary(self, analysis: LHBSeatAnalysis, summary_df) -> LHBSeatAnalysis:
        """Estimate seat analysis from summary data when detailed seats unavailable"""
        try:
            row = summary_df.iloc[0]
            
            # Get available amounts
            net_buy = row.get('龙虎榜净买额', row.get('净买额', 0))
            buy_amount = row.get('龙虎榜买入额', row.get('买入额', 0))
            sell_amount = row.get('龙虎榜卖出额', row.get('卖出额', 0))
            inst_buy = row.get('机构买入', 0)
            inst_sell = row.get('机构卖出', 0)
            
            # Convert to 万元
            analysis.total_net_buy = float(net_buy) / 10000 if net_buy else 0
            analysis.institution_net_buy = (float(inst_buy) - float(inst_sell)) / 10000 if inst_buy and inst_sell else 0
            analysis.has_institution_buy = analysis.institution_net_buy > 0
            
            # Generate signal based on available data
            self._generate_signal(analysis)
            
            return analysis
            
        except Exception as e:
            logger.warning(f"[LHB席位] 从摘要估算失败: {e}")
            return analysis
    
    def _calculate_metrics(self, analysis: LHBSeatAnalysis):
        """Calculate aggregated metrics from seat details"""
        for seat in analysis.buy_seats + analysis.sell_seats:
            net = seat.net_amount or 0
            
            if seat.seat_type == "institution":
                analysis.institution_net_buy += net
                if net > 0:
                    analysis.has_institution_buy = True
            elif seat.seat_type == "northbound":
                analysis.northbound_net_buy += net
                if net > 0:
                    analysis.has_northbound_buy = True
            elif seat.seat_type == "hot_money":
                analysis.hot_money_net_buy += net
                if net > 0:
                    analysis.has_hot_money_buy = True
            
            # Track known seats
            if seat.alias:
                analysis.known_seats.append(f"{seat.alias}({seat.style})")
        
        # Total net buy
        analysis.total_net_buy = (
            analysis.institution_net_buy + 
            analysis.hot_money_net_buy + 
            analysis.northbound_net_buy
        )
        
        # Generate signal
        self._generate_signal(analysis)
    
    def _generate_signal(self, analysis: LHBSeatAnalysis):
        """Generate trading signal based on seat activity"""
        reasons = []
        signals = []
        
        # Institution buying is bullish
        if analysis.institution_net_buy > 1000:  # > 1000万
            signals.append(1)
            reasons.append(f"机构净买入{analysis.institution_net_buy:.0f}万")
        elif analysis.institution_net_buy > 0:
            signals.append(0.5)
            reasons.append(f"机构小幅净买入{analysis.institution_net_buy:.0f}万")
        
        # Northbound buying is bullish
        if analysis.northbound_net_buy > 500:
            signals.append(0.8)
            reasons.append(f"北向资金净买入{analysis.northbound_net_buy:.0f}万")
        
        # Known hot money seats
        if analysis.known_seats:
            bullish_seats = [s for s in analysis.buy_seats if s.reputation == "bullish"]
            if bullish_seats:
                signals.append(0.7)
                reasons.append(f"知名游资买入: {', '.join([s.alias for s in bullish_seats[:2]])}")
            
            aggressive_seats = [s for s in analysis.buy_seats if s.reputation == "aggressive"]
            if aggressive_seats:
                signals.append(0.5)
                reasons.append(f"激进游资参与: {', '.join([s.alias for s in aggressive_seats[:2]])}")
        
        # Retail heavy selling (拉萨系) is bearish
        lhasa_sell = sum(
            s.net_amount or 0 
            for s in analysis.sell_seats 
            if s.alias and "拉萨" in s.alias
        )
        if lhasa_sell < -500:
            signals.append(-0.3)
            reasons.append(f"散户席位大幅卖出")
        
        # Calculate final signal
        if not signals:
            analysis.seat_signal = "neutral"
            analysis.signal_reason = "无明显席位信号"
        else:
            avg_signal = sum(signals) / len(signals)
            if avg_signal >= 0.6:
                analysis.seat_signal = "bullish"
            elif avg_signal >= 0.3:
                analysis.seat_signal = "slightly_bullish"
            elif avg_signal <= -0.3:
                analysis.seat_signal = "bearish"
            else:
                analysis.seat_signal = "neutral"
            
            analysis.signal_reason = "; ".join(reasons[:3])
    
    def analyze_sector_concentration(self, days: int = 1) -> List[SectorConcentration]:
        """
        Analyze sector concentration in LHB data
        
        Identifies sectors with multiple stocks appearing on LHB,
        indicating potential capital rotation.
        
        Args:
            days: Number of recent days to analyze
            
        Returns:
            List of SectorConcentration sorted by stock count
        """
        from src.hot_stocks_analyzer import HotStocksAnalyzer
        
        ak = self._get_akshare()
        
        try:
            today = datetime.now()
            all_records = []
            
            for i in range(days):
                check_date = today - timedelta(days=i)
                date_str = check_date.strftime('%Y%m%d')
                
                try:
                    df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
                    if df is not None and not df.empty:
                        all_records.append(df)
                except Exception as e:
                    logger.debug(f"[板块集中度] 获取 {date_str} 数据失败: {e}")
            
            if not all_records:
                return []
            
            combined_df = concat_df(all_records)
            if combined_df.empty:
                return []
            
            # Get sector info for each stock
            sector_map = self._get_stock_sectors(combined_df['代码'].unique().tolist())
            
            # Aggregate by sector
            sector_data = defaultdict(lambda: {
                'codes': [],
                'names': [],
                'net_buys': []
            })
            
            for _, row in combined_df.iterrows():
                code = str(row.get('代码', ''))
                name = str(row.get('名称', ''))
                net_buy = float(row.get('龙虎榜净买额', row.get('净买额', 0))) / 10000
                
                sector = sector_map.get(code, '其他')
                
                sector_data[sector]['codes'].append(code)
                sector_data[sector]['names'].append(name)
                sector_data[sector]['net_buys'].append(net_buy)
            
            # Build result
            results = []
            for sector, data in sector_data.items():
                if len(data['codes']) >= 2:  # At least 2 stocks from same sector
                    concentration = SectorConcentration(
                        sector_name=sector,
                        stock_count=len(data['codes']),
                        total_net_buy=sum(data['net_buys']),
                        stock_codes=data['codes'],
                        stock_names=data['names'],
                    )
                    results.append(concentration)
            
            # Sort by stock count
            results.sort(key=lambda x: x.stock_count, reverse=True)
            
            return results[:10]  # Top 10 sectors
            
        except Exception as e:
            logger.error(f"[板块集中度] 分析失败: {e}")
            return []
    
    def _get_stock_sectors(self, codes: List[str]) -> Dict[str, str]:
        """
        Get sector/industry for a list of stocks
        
        Uses akshare stock info API
        """
        ak = self._get_akshare()
        sector_map = {}
        
        try:
            # Try to get industry info
            # Note: This is a simplified approach
            # In production, should use local cache or batch API
            for code in codes[:20]:  # Limit to avoid rate limiting
                try:
                    info_df = ak.stock_individual_info_em(symbol=code)
                    if info_df is not None and not info_df.empty:
                        industry_row = info_df[info_df['item'] == '行业']
                        if not industry_row.empty:
                            sector_map[code] = str(industry_row.iloc[0]['value'])
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[板块映射] 获取行业信息失败: {e}")
        
        return sector_map
    
    def generate_seat_report(self, analysis: LHBSeatAnalysis) -> List[str]:
        """
        Generate markdown report for seat analysis
        
        Args:
            analysis: LHBSeatAnalysis object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"### 🐉 龙虎榜席位分析 ({analysis.name} {analysis.code})",
            "",
            f"> 分析日期: {analysis.analysis_date} | 收盘价: {analysis.close_price:.2f} | 涨跌幅: {analysis.change_pct:+.2f}%",
            "",
        ]
        
        # Seat signal
        signal_emoji = {
            "bullish": "🟢",
            "slightly_bullish": "🟡",
            "neutral": "⚪",
            "bearish": "🔴",
        }
        emoji = signal_emoji.get(analysis.seat_signal, "⚪")
        lines.append(f"**席位信号**: {emoji} {analysis.seat_signal} | {analysis.signal_reason}")
        lines.append("")
        
        # Aggregated metrics
        lines.append("#### 📊 资金结构")
        lines.append("")
        lines.append("| 类型 | 净买入(万) | 说明 |")
        lines.append("|------|-----------|------|")
        
        if analysis.institution_net_buy != 0:
            inst_status = "机构净买入" if analysis.institution_net_buy > 0 else "机构净卖出"
            lines.append(f"| 机构 | {analysis.institution_net_buy:+.0f} | {inst_status} |")
        
        if analysis.northbound_net_buy != 0:
            nb_status = "北向净买入" if analysis.northbound_net_buy > 0 else "北向净卖出"
            lines.append(f"| 北向资金 | {analysis.northbound_net_buy:+.0f} | {nb_status} |")
        
        if analysis.hot_money_net_buy != 0:
            hm_status = "游资净买入" if analysis.hot_money_net_buy > 0 else "游资净卖出"
            lines.append(f"| 游资 | {analysis.hot_money_net_buy:+.0f} | {hm_status} |")
        
        lines.append(f"| **合计** | **{analysis.total_net_buy:+.0f}** | - |")
        lines.append("")
        
        # Buy seats
        if analysis.buy_seats:
            lines.append("#### 🟢 买入席位 TOP5")
            lines.append("")
            lines.append("| 席位 | 类型 | 买入(万) | 净买(万) |")
            lines.append("|------|------|----------|----------|")
            
            for seat in analysis.buy_seats[:5]:
                name = seat.alias or seat.seat_name[:15] + "..."
                buy_str = f"{seat.buy_amount:.0f}" if seat.buy_amount else "-"
                net_str = f"{seat.net_amount:+.0f}" if seat.net_amount else "-"
                lines.append(f"| {name} | {seat.seat_type} | {buy_str} | {net_str} |")
            
            lines.append("")
        
        # Known seats highlight
        if analysis.known_seats:
            lines.append("#### ⭐ 知名席位")
            lines.append("")
            for seat_info in analysis.known_seats[:5]:
                lines.append(f"- {seat_info}")
            lines.append("")
        
        return lines


def concat_df(dfs: List) -> Any:
    """Concatenate DataFrames"""
    import pandas as pd
    if not dfs:
        return pd.DataFrame()
    
    result = pd.concat(dfs, ignore_index=True)
    # Deduplicate by code
    if '代码' in result.columns:
        result = result.drop_duplicates(subset=['代码'])
    return result


# Singleton instance
_analyzer_instance: Optional[LHBSeatAnalyzer] = None


def get_lhb_seat_analyzer() -> LHBSeatAnalyzer:
    """Get LHBSeatAnalyzer singleton instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = LHBSeatAnalyzer()
    return _analyzer_instance