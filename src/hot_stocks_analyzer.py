# -*- coding: utf-8 -*-
"""
Hot Stocks and Dragon-Tiger List Analyzer

Provides real-time hot stocks (top gainers) and dragon-tiger list (lhb) data.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class HotStock:
    """Hot stock data (top gainer)"""
    code: str
    name: str
    change_pct: float
    price: float
    volume: Optional[float] = None  # 成交量（万手）
    amount: Optional[float] = None  # 成交额（万元）
    turnover_rate: Optional[float] = None  # 换手率
    reason: Optional[str] = None  # 涨停原因


@dataclass
class LHBRecord:
    """Dragon-Tiger List (龙虎榜) record"""
    code: str
    name: str
    close_price: float
    change_pct: float
    turnover_rate: Optional[float] = None
    reason: Optional[str] = None  # 上榜原因
    net_buy: Optional[float] = None  # 净买入（万元）
    buy_amount: Optional[float] = None  # 买入金额（万元）
    sell_amount: Optional[float] = None  # 卖出金额（万元）
    institution_buy: Optional[float] = None  # 机构买入（万元）
    institution_sell: Optional[float] = None  # 机构卖出（万元）


class HotStocksAnalyzer:
    """
    Hot Stocks and Dragon-Tiger List Analyzer
    
    Uses akshare to fetch:
    - Real-time top gainers (涨幅榜)
    - Dragon-tiger list (龙虎榜)
    """
    
    def __init__(self):
        self._akshare = None
        self._lhb_cache = None  # Cache for LHB records
        self._lhb_cache_time = None  # Cache timestamp
    
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
    
    def get_hot_stocks(self, n: int = 20) -> List[HotStock]:
        """
        Get top gainers (涨幅榜前N只股票)
        
        Args:
            n: Number of stocks to return
            
        Returns:
            List of HotStock objects
        """
        try:
            ak = self._get_akshare()
            
            # 获取实时涨幅榜
            df = ak.stock_zh_a_spot_em()
            
            if df is None or df.empty:
                logger.warning("No data returned from akshare")
                return []
            
            # 按涨跌幅排序
            df = df.sort_values(by='涨跌幅', ascending=False)

            # 取前N只
            df = df.head(n)
            
            stocks = []
            for _, row in df.iterrows():
                try:
                    stock = HotStock(
                        code=str(row.get('代码', '')),
                        name=str(row.get('名称', '')),
                        change_pct=float(row.get('涨跌幅', 0)),
                        price=float(row.get('最新价', 0)),
                        volume=float(row.get('成交量', 0)) / 100000 if row.get('成交量') else None,  # 转万手
                        amount=float(row.get('成交额', 0)) / 10000 if row.get('成交额') else None,  # 转万元
                        turnover_rate=float(row.get('换手率', 0)) if row.get('换手率') else None,
                    )
                    stocks.append(stock)
                except Exception as e:
                    logger.debug(f"Error parsing stock row: {e}")
                    continue
            
            logger.info(f"Got {len(stocks)} hot stocks")
            return stocks
            
        except Exception as e:
            logger.error(f"Failed to get hot stocks: {e}")
            return []
    
    def get_dragon_tiger_list(self, days: int = 1) -> List[LHBRecord]:
        """
        Get dragon-tiger list (龙虎榜) data
        
        Args:
            days: Number of recent days to fetch
            
        Returns:
            List of LHBRecord objects
        """
        try:
            ak = self._get_akshare()
            
            records = []
            today = datetime.now()
            
            for i in range(days):
                date = today - timedelta(days=i)
                date_str = date.strftime('%Y%m%d')
                
                try:
                    # 获取龙虎榜数据
                    df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
                    
                    if df is None or df.empty:
                        logger.debug(f"No LHB data for {date_str}")
                        continue
                    
                    for _, row in df.iterrows():
                        try:
                            # akshare column names changed: 净买额 -> 龙虎榜净买额
                            net_buy_val = row.get('龙虎榜净买额') or row.get('净买额')
                            buy_amount_val = row.get('龙虎榜买入额') or row.get('买入额')
                            sell_amount_val = row.get('龙虎榜卖出额') or row.get('卖出额')
                            
                            record = LHBRecord(
                                code=str(row.get('代码', '')),
                                name=str(row.get('名称', '')),
                                close_price=float(row.get('收盘价', 0)) if row.get('收盘价') else 0,
                                change_pct=float(row.get('涨跌幅', 0)) if row.get('涨跌幅') else 0,
                                turnover_rate=float(row.get('换手率', 0)) if row.get('换手率') else None,
                                reason=str(row.get('上榜原因', '')) if row.get('上榜原因') else None,
                                net_buy=float(net_buy_val) / 10000 if net_buy_val else None,
                                buy_amount=float(buy_amount_val) / 10000 if buy_amount_val else None,
                                sell_amount=float(sell_amount_val) / 10000 if sell_amount_val else None,
                            )
                            records.append(record)
                        except Exception as e:
                            logger.debug(f"Error parsing LHB row: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error fetching LHB for {date_str}: {e}")
                    continue
            
            # 去重（按代码）
            seen = set()
            unique_records = []
            for r in records:
                if r.code not in seen:
                    seen.add(r.code)
                    unique_records.append(r)
            
            logger.info(f"Got {len(unique_records)} LHB records")
            return unique_records
            
        except Exception as e:
            logger.error(f"Failed to get dragon-tiger list: {e}")
            return []
    
    def generate_hot_stocks_section(self, n: int = 20) -> List[str]:
        """
        Generate markdown section for hot stocks
        
        Args:
            n: Number of hot stocks to include
            
        Returns:
            List of markdown lines
        """
        lines = [
            "## 🔥 热门股涨幅榜",
            "",
            f"> 涨幅榜前 {n} 只股票 | 数据时间：{datetime.now().strftime('%H:%M:%S')}",
            "",
            "| 排名 | 代码 | 名称 | 涨幅 | 现价 | 成交额 | 换手率 |",
            "|------|------|------|------|------|--------|--------|",
        ]
        
        stocks = self.get_hot_stocks(n)
        
        if not stocks:
            lines.append("*暂无数据*")
            return lines
        
        for i, stock in enumerate(stocks, 1):
            change_emoji = "🚀" if stock.change_pct >= 9.9 else ("📈" if stock.change_pct > 0 else "📉")
            amount_str = f"{stock.amount:.0f}万" if stock.amount else "-"
            turnover_str = f"{stock.turnover_rate:.2f}%" if stock.turnover_rate else "-"
            
            lines.append(
                f"| {i} | {stock.code} | {stock.name} | {change_emoji} {stock.change_pct:.2f}% | "
                f"{stock.price:.2f} | {amount_str} | {turnover_str} |"
            )
        
        lines.extend([
            "",
            "### 💡 操作建议",
            "",
            "- **追高需谨慎**：涨幅过大的股票风险较高，注意回调风险",
            "- **关注成交量**：放量上涨更具持续性，缩量上涨需警惕",
            "- **结合基本面**：热门股需关注公司基本面和行业逻辑",
            "",
        ])
        
        return lines
    
    def get_lhb_stock_codes(
        self, 
        days: int = 1, 
        max_count: int = 10,
        min_net_buy: float = 0,
        sort_by: str = "net_buy"
    ) -> List[str]:
        """
        Get stock codes from dragon-tiger list for analysis
        
        Args:
            days: Number of recent days to fetch
            max_count: Maximum number of stocks to return
            min_net_buy: Minimum net buy amount (万元), filter out stocks below this
            sort_by: Sort field - "net_buy" or "change_pct"
            
        Returns:
            List of stock codes (uppercase, for analysis pipeline)
        """
        records = self.get_dragon_tiger_list(days)
        
        if not records:
            logger.info("No LHB records found")
            return []
        
        # Filter by min_net_buy
        if min_net_buy > 0:
            records = [r for r in records if r.net_buy and r.net_buy >= min_net_buy]
            logger.info(f"Filtered {len(records)} LHB records with net_buy >= {min_net_buy}万")
        
        # Sort
        if sort_by == "net_buy":
            records = sorted(records, key=lambda x: x.net_buy or 0, reverse=True)
        elif sort_by == "change_pct":
            records = sorted(records, key=lambda x: abs(x.change_pct) if x.change_pct else 0, reverse=True)
        
        # Get codes (uppercase for consistency)
        codes = [r.code.upper() for r in records[:max_count]]
        
        logger.info(f"Selected {len(codes)} LHB stocks for analysis: {codes}")
        return codes
    
    def get_lhb_records_for_analysis(self, days: int = 1) -> List[LHBRecord]:
        """
        Get LHB records with all details for context enhancement
        
        Args:
            days: Number of recent days to fetch
            
        Returns:
            List of LHBRecord objects (deduplicated by code)
        """
        return self.get_dragon_tiger_list(days)
    
    def generate_lhb_section(self, days: int = 1) -> List[str]:
        """
        Generate markdown section for dragon-tiger list
        
        Args:
            days: Number of days to include
            
        Returns:
            List of markdown lines
        """
        lines = [
            "## 🐉 龙虎榜",
            "",
            f"> 最近 {days} 天龙虎榜数据",
            "",
        ]
        
        records = self.get_dragon_tiger_list(days)
        
        if not records:
            lines.append("*暂无龙虎榜数据*")
            return lines
        
        # 按净买入排序
        records = sorted(records, key=lambda x: x.net_buy or 0, reverse=True)
        
        lines.extend([
            "### 📊 净买入 TOP 10",
            "",
            "| 代码 | 名称 | 涨幅 | 净买入 | 上榜原因 |",
            "|------|------|------|--------|----------|",
        ])
        
        for record in records[:10]:
            change_str = f"{record.change_pct:.2f}%"
            net_buy_str = f"{record.net_buy:.0f}万" if record.net_buy else "-"
            reason_str = (record.reason[:15] + "...") if record.reason and len(record.reason) > 15 else (record.reason or "-")
            
            lines.append(
                f"| {record.code} | {record.name} | {change_str} | {net_buy_str} | {reason_str} |"
            )
        
        lines.extend([
            "",
            "### 💡 龙虎榜解读",
            "",
            "- **机构买入**：机构净买入个股通常具有较好的基本面支撑",
            "- **游资活跃**：游资大额买入可能是短期炒作，需谨慎对待",
            "- **上榜原因**：关注涨停、跌停、换手率异常等上榜原因",
            "",
        ])
        
        return lines


def get_hot_stocks_analyzer() -> HotStocksAnalyzer:
    """Get HotStocksAnalyzer instance"""
    return HotStocksAnalyzer()