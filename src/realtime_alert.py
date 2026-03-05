# -*- coding: utf-8 -*-
"""
Realtime Alert System (异动实时推送)

Detects and alerts on significant stock movements:
- Volume breakout (放量突破)
- Support/Resistance break (支撑/压力突破)
- Large LHB net buy (龙虎榜巨额净买入)
- Price spike/drop (急涨急跌)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Alert types"""
    VOLUME_BREAKOUT = "volume_breakout"       # 放量突破
    SUPPORT_BREAK = "support_break"           # 下破支撑
    RESISTANCE_BREAK = "resistance_break"     # 上破压力
    LHB_LARGE_BUY = "lhb_large_buy"           # 龙虎榜大买
    LHB_LARGE_SELL = "lhb_large_sell"         # 龙虎榜大卖
    PRICE_SPIKE = "price_spike"               # 急涨
    PRICE_DROP = "price_drop"                 # 急跌
    TURNOVER_HIGH = "turnover_high"           # 换手异常


class AlertLevel(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"    # 重要：需立即关注
    HIGH = "high"           # 高：建议当日关注
    MEDIUM = "medium"       # 中：可稍后关注
    LOW = "low"             # 低：仅供参考


@dataclass
class StockAlert:
    """A single stock alert"""
    stock_code: str
    stock_name: str
    alert_type: AlertType
    alert_level: AlertLevel
    
    # Alert details
    title: str                           # Alert title
    description: str                     # Detailed description
    
    # Price data
    current_price: float = 0.0
    change_pct: float = 0.0
    volume_ratio: float = 0.0            # 量比
    turnover_rate: float = 0.0           # 换手率
    
    # Thresholds
    trigger_value: float = 0.0           # Value that triggered alert
    threshold: float = 0.0               # Threshold value
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Action suggestion
    action_hint: str = ""
    
    # Additional data
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertScanResult:
    """Result of alert scanning"""
    scan_time: datetime
    total_alerts: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    
    # Alerts by type
    alerts: List[StockAlert] = field(default_factory=list)
    
    # Summary
    summary: str = ""


class RealtimeAlertScanner:
    """
    Realtime Alert Scanner
    
    Scans for significant stock movements and generates alerts.
    Supports:
    - Volume breakout detection
    - Support/resistance break detection
    - LHB large transaction alerts
    - Price spike/drop alerts
    """
    
    # Alert thresholds
    VOLUME_BREAKOUT_RATIO = 2.0          # 量比>=2视为放量
    PRICE_SPIKE_THRESHOLD = 5.0          # 涨幅>=5%视为急涨
    PRICE_DROP_THRESHOLD = -5.0          # 跌幅>=5%视为急跌
    TURNOVER_HIGH_THRESHOLD = 10.0       # 换手>=10%视为异常
    LHB_LARGE_BUY_THRESHOLD = 5000       # 龙虎榜净买入>=5000万视为大买
    
    def __init__(self):
        self._akshare = None
        self._alert_handlers: List[Callable[[StockAlert], None]] = []
    
    def _get_akshare(self):
        """Lazy import akshare"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare
    
    def register_alert_handler(self, handler: Callable[[StockAlert], None]):
        """Register a handler to process alerts"""
        self._alert_handlers.append(handler)
    
    def scan_all(self, watch_list: List[str] = None) -> AlertScanResult:
        """
        Scan all stocks for alerts
        
        Args:
            watch_list: List of stock codes to scan (optional)
            
        Returns:
            AlertScanResult with all detected alerts
        """
        result = AlertScanResult(scan_time=datetime.now())
        
        # Get market data
        market_data = self._get_market_data()
        
        if market_data is None or market_data.empty:
            logger.warning("[异动扫描] 无法获取市场数据")
            result.summary = "无法获取市场数据"
            return result
        
        alerts = []
        
        # Scan each stock
        stocks_to_scan = watch_list if watch_list else []
        
        for _, row in market_data.iterrows():
            code = str(row.get('代码', ''))
            
            # If watch_list specified, only scan those stocks
            if stocks_to_scan and code not in stocks_to_scan:
                continue
            
            stock_alerts = self._scan_single_stock(row)
            alerts.extend(stock_alerts)
        
        # Sort by level
        level_order = {AlertLevel.CRITICAL: 0, AlertLevel.HIGH: 1, AlertLevel.MEDIUM: 2, AlertLevel.LOW: 3}
        alerts.sort(key=lambda x: level_order.get(x.alert_level, 99))
        
        result.alerts = alerts
        result.total_alerts = len(alerts)
        result.critical_count = sum(1 for a in alerts if a.alert_level == AlertLevel.CRITICAL)
        result.high_count = sum(1 for a in alerts if a.alert_level == AlertLevel.HIGH)
        result.medium_count = sum(1 for a in alerts if a.alert_level == AlertLevel.MEDIUM)
        
        result.summary = self._generate_summary(result)
        
        logger.info(f"[异动扫描] 发现 {result.total_alerts} 条异动，"
                   f"重要 {result.critical_count} 条，高 {result.high_count} 条")
        
        # Trigger handlers
        for alert in alerts:
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"[异动扫描] 处理器执行失败: {e}")
        
        return result
    
    def scan_stock(self, stock_code: str, stock_name: str = "") -> List[StockAlert]:
        """
        Scan a single stock for alerts
        
        Args:
            stock_code: Stock code
            stock_name: Stock name (optional)
            
        Returns:
            List of StockAlert objects
        """
        ak = self._get_akshare()
        
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return []
            
            row = df[df['代码'] == stock_code]
            if row.empty:
                return []
            
            return self._scan_single_stock(row.iloc[0])
            
        except Exception as e:
            logger.error(f"[异动扫描] 扫描 {stock_code} 失败: {e}")
            return []
    
    def _get_market_data(self):
        """Get real-time market data"""
        ak = self._get_akshare()
        
        try:
            logger.info("[异动扫描] 获取市场行情...")
            return ak.stock_zh_a_spot_em()
        except Exception as e:
            logger.error(f"[异动扫描] 获取市场数据失败: {e}")
            return None
    
    def _scan_single_stock(self, row) -> List[StockAlert]:
        """Scan a single stock for alerts"""
        alerts = []
        
        try:
            code = str(row.get('代码', ''))
            name = str(row.get('名称', ''))
            change_pct = float(row.get('涨跌幅', 0))
            volume_ratio = float(row.get('量比', 0)) if '量比' in row else 0
            turnover_rate = float(row.get('换手率', 0)) if '换手率' in row else 0
            current_price = float(row.get('最新价', 0))
            
            # 1. Volume breakout alert
            if volume_ratio >= self.VOLUME_BREAKOUT_RATIO:
                alert = self._create_volume_breakout_alert(
                    code, name, change_pct, current_price, volume_ratio, turnover_rate
                )
                if alert:
                    alerts.append(alert)
            
            # 2. Price spike alert
            if change_pct >= self.PRICE_SPIKE_THRESHOLD:
                alert = self._create_price_spike_alert(
                    code, name, change_pct, current_price, volume_ratio
                )
                if alert:
                    alerts.append(alert)
            
            # 3. Price drop alert
            if change_pct <= self.PRICE_DROP_THRESHOLD:
                alert = self._create_price_drop_alert(
                    code, name, change_pct, current_price, volume_ratio
                )
                if alert:
                    alerts.append(alert)
            
            # 4. High turnover alert
            if turnover_rate >= self.TURNOVER_HIGH_THRESHOLD:
                alert = self._create_turnover_alert(
                    code, name, change_pct, current_price, turnover_rate
                )
                if alert:
                    alerts.append(alert)
            
        except Exception as e:
            logger.debug(f"[异动扫描] 扫描股票失败: {e}")
        
        return alerts
    
    def _create_volume_breakout_alert(
        self, code: str, name: str, change_pct: float, 
        price: float, volume_ratio: float, turnover: float
    ) -> Optional[StockAlert]:
        """Create volume breakout alert"""
        
        # Only alert if price is up
        if change_pct <= 0:
            return None
        
        level = AlertLevel.HIGH if change_pct >= 3 else AlertLevel.MEDIUM
        
        return StockAlert(
            stock_code=code,
            stock_name=name,
            alert_type=AlertType.VOLUME_BREAKOUT,
            alert_level=level,
            title=f"放量突破: {name}",
            description=f"{name} 量比{volume_ratio:.1f}倍，涨幅{change_pct:+.1f}%，换手{turnover:.1f}%",
            current_price=price,
            change_pct=change_pct,
            volume_ratio=volume_ratio,
            turnover_rate=turnover,
            trigger_value=volume_ratio,
            threshold=self.VOLUME_BREAKOUT_RATIO,
            action_hint="放量上涨，关注突破有效性，确认成交量持续放大则可跟进",
        )
    
    def _create_price_spike_alert(
        self, code: str, name: str, change_pct: float,
        price: float, volume_ratio: float
    ) -> Optional[StockAlert]:
        """Create price spike alert"""
        
        level = AlertLevel.CRITICAL if change_pct >= 7 else AlertLevel.HIGH
        
        return StockAlert(
            stock_code=code,
            stock_name=name,
            alert_type=AlertType.PRICE_SPIKE,
            alert_level=level,
            title=f"急涨异动: {name}",
            description=f"{name} 急涨{change_pct:+.1f}%，量比{volume_ratio:.1f}倍",
            current_price=price,
            change_pct=change_pct,
            volume_ratio=volume_ratio,
            trigger_value=change_pct,
            threshold=self.PRICE_SPIKE_THRESHOLD,
            action_hint="急涨异动，注意追高风险，观察是否放量确认",
        )
    
    def _create_price_drop_alert(
        self, code: str, name: str, change_pct: float,
        price: float, volume_ratio: float
    ) -> Optional[StockAlert]:
        """Create price drop alert"""
        
        level = AlertLevel.CRITICAL if change_pct <= -7 else AlertLevel.HIGH
        
        return StockAlert(
            stock_code=code,
            stock_name=name,
            alert_type=AlertType.PRICE_DROP,
            alert_level=level,
            title=f"急跌异动: {name}",
            description=f"{name} 急跌{change_pct:.1f}%，量比{volume_ratio:.1f}倍",
            current_price=price,
            change_pct=change_pct,
            volume_ratio=volume_ratio,
            trigger_value=abs(change_pct),
            threshold=abs(self.PRICE_DROP_THRESHOLD),
            action_hint="急跌异动，检查是否有利空消息，支撑位关注是否有效",
        )
    
    def _create_turnover_alert(
        self, code: str, name: str, change_pct: float,
        price: float, turnover: float
    ) -> Optional[StockAlert]:
        """Create high turnover alert"""
        
        level = AlertLevel.MEDIUM
        
        return StockAlert(
            stock_code=code,
            stock_name=name,
            alert_type=AlertType.TURNOVER_HIGH,
            alert_level=level,
            title=f"换手异常: {name}",
            description=f"{name} 换手率达{turnover:.1f}%，涨幅{change_pct:+.1f}%",
            current_price=price,
            change_pct=change_pct,
            turnover_rate=turnover,
            trigger_value=turnover,
            threshold=self.TURNOVER_HIGH_THRESHOLD,
            action_hint="换手异常活跃，主力可能进出，关注后续走势",
        )
    
    def check_lhb_alert(self, stock_code: str, stock_name: str = "") -> Optional[StockAlert]:
        """
        Check LHB data for large transaction alerts
        
        Args:
            stock_code: Stock code
            stock_name: Stock name
            
        Returns:
            StockAlert if significant LHB activity detected
        """
        try:
            from .lhb_seat_analyzer import get_lhb_seat_analyzer
            
            analyzer = get_lhb_seat_analyzer()
            lhb_data = analyzer.get_lhb_stock_seats(stock_code)
            
            if lhb_data is None:
                return None
            
            net_buy = lhb_data.total_net_buy
            
            if net_buy >= self.LHB_LARGE_BUY_THRESHOLD:
                return StockAlert(
                    stock_code=stock_code,
                    stock_name=stock_name or lhb_data.stock_name,
                    alert_type=AlertType.LHB_LARGE_BUY,
                    alert_level=AlertLevel.CRITICAL,
                    title=f"龙虎榜大买: {stock_name}",
                    description=f"{stock_name} 龙虎榜净买入{net_buy:.0f}万，知名游资参与",
                    trigger_value=net_buy,
                    threshold=self.LHB_LARGE_BUY_THRESHOLD,
                    action_hint="龙虎榜大额净买入，主力看好，可跟踪后续走势",
                    extra={'lhb_data': lhb_data},
                )
            
            elif net_buy <= -self.LHB_LARGE_BUY_THRESHOLD:
                return StockAlert(
                    stock_code=stock_code,
                    stock_name=stock_name or lhb_data.stock_name,
                    alert_type=AlertType.LHB_LARGE_SELL,
                    alert_level=AlertLevel.HIGH,
                    title=f"龙虎榜大卖: {stock_name}",
                    description=f"{stock_name} 龙虎榜净卖出{abs(net_buy):.0f}万",
                    trigger_value=abs(net_buy),
                    threshold=self.LHB_LARGE_BUY_THRESHOLD,
                    action_hint="龙虎榜大额净卖出，主力撤离，注意风险",
                    extra={'lhb_data': lhb_data},
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"[异动扫描] 检查龙虎榜失败: {e}")
            return None
    
    def _generate_summary(self, result: AlertScanResult) -> str:
        """Generate alert summary"""
        if result.total_alerts == 0:
            return "暂无异动"
        
        parts = []
        
        if result.critical_count > 0:
            parts.append(f"重要异动 {result.critical_count} 条")
        if result.high_count > 0:
            parts.append(f"高优先级 {result.high_count} 条")
        if result.medium_count > 0:
            parts.append(f"中优先级 {result.medium_count} 条")
        
        return " | ".join(parts)
    
    def generate_alert_report(self, result: AlertScanResult) -> List[str]:
        """
        Generate markdown report for alerts
        
        Args:
            result: AlertScanResult object
            
        Returns:
            List of markdown lines
        """
        lines = [
            f"## 🚨 异动实时推送 ({result.scan_time.strftime('%Y-%m-%d %H:%M')})",
            "",
        ]
        
        # Summary
        lines.append(f"> {result.summary}")
        lines.append("")
        
        if not result.alerts:
            lines.append("暂无异动信息")
            return lines
        
        # Group by level
        critical_alerts = [a for a in result.alerts if a.alert_level == AlertLevel.CRITICAL]
        high_alerts = [a for a in result.alerts if a.alert_level == AlertLevel.HIGH]
        medium_alerts = [a for a in result.alerts if a.alert_level == AlertLevel.MEDIUM]
        
        # Critical alerts
        if critical_alerts:
            lines.append("### 🔴 重要异动")
            lines.append("")
            for alert in critical_alerts:
                lines.append(f"**{alert.title}**")
                lines.append(f"- {alert.description}")
                lines.append(f"- 💡 {alert.action_hint}")
                lines.append("")
        
        # High alerts
        if high_alerts:
            lines.append("### 🟠 高优先级异动")
            lines.append("")
            for alert in high_alerts:
                lines.append(f"**{alert.title}**")
                lines.append(f"- {alert.description}")
                lines.append(f"- 💡 {alert.action_hint}")
                lines.append("")
        
        # Medium alerts
        if medium_alerts:
            lines.append("### 🟡 中优先级异动")
            lines.append("")
            for alert in medium_alerts:
                lines.append(f"- **{alert.title}**: {alert.description}")
        
        return lines


# Singleton
_scanner_instance: Optional[RealtimeAlertScanner] = None


def get_realtime_alert_scanner() -> RealtimeAlertScanner:
    """Get RealtimeAlertScanner singleton"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = RealtimeAlertScanner()
    return _scanner_instance