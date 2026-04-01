# -*- coding: utf-8 -*-
"""
===================================
股票数据访问层
===================================

职责：
1. 封装股票数据的数据库操作
2. 提供日线数据查询接口
"""

import logging
from datetime import date
from typing import Optional, List, Dict, Any

import pandas as pd
from sqlalchemy import and_, desc, func, select

from src.storage import DatabaseManager, StockDaily

logger = logging.getLogger(__name__)


class StockRepository:
    """
    股票数据访问层
    
    封装 StockDaily 表的数据库操作
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化数据访问层
        
        Args:
            db_manager: 数据库管理器（可选，默认使用单例）
        """
        self.db = db_manager or DatabaseManager.get_instance()
    
    def get_latest(self, code: str, days: int = 2) -> List[StockDaily]:
        """
        获取最近 N 天的数据
        
        Args:
            code: 股票代码
            days: 获取天数
            
        Returns:
            StockDaily 对象列表（按日期降序）
        """
        try:
            return self.db.get_latest_data(code, days)
        except Exception as e:
            logger.error(f"获取最新数据失败: {e}")
            return []
    
    def get_range(
        self,
        code: str,
        start_date: date,
        end_date: date
    ) -> List[StockDaily]:
        """
        获取指定日期范围的数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            StockDaily 对象列表
        """
        try:
            return self.db.get_data_range(code, start_date, end_date)
        except Exception as e:
            logger.error(f"获取日期范围数据失败: {e}")
            return []
    
    def save_dataframe(
        self,
        df: pd.DataFrame,
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        保存 DataFrame 到数据库
        
        Args:
            df: 包含日线数据的 DataFrame
            code: 股票代码
            data_source: 数据来源
            
        Returns:
            保存的记录数
        """
        try:
            return self.db.save_daily_data(df, code, data_source)
        except Exception as e:
            logger.error(f"保存日线数据失败: {e}")
            return 0
    
    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        检查是否有指定日期的数据
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            是否存在数据
        """
        try:
            return self.db.has_today_data(code, target_date)
        except Exception as e:
            logger.error(f"检查数据存在失败: {e}")
            return False
    
    def get_analysis_context(
        self, 
        code: str, 
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取分析上下文
        
        Args:
            code: 股票代码
            target_date: 目标日期
            
        Returns:
            分析上下文字典
        """
        try:
            return self.db.get_analysis_context(code, target_date)
        except Exception as e:
            logger.error(f"获取分析上下文失败: {e}")
            return None

    def get_start_daily(self, *, code: str, analysis_date: date) -> Optional[StockDaily]:
        """Return StockDaily for analysis_date (preferred) or nearest previous date."""
        with self.db.get_session() as session:
            row = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date <= analysis_date))
                .order_by(desc(StockDaily.date))
                .limit(1)
            ).scalar_one_or_none()
            return row

    def get_forward_bars(self, *, code: str, analysis_date: date, eval_window_days: int) -> List[StockDaily]:
        """Return forward daily bars after analysis_date, up to eval_window_days."""
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date > analysis_date))
                .order_by(StockDaily.date)
                .limit(eval_window_days)
            ).scalars().all()
            return list(rows)

    def get_latest_trade_date(self, code: str) -> Optional[date]:
        """Return the latest stored trade date for one stock."""
        with self.db.get_session() as session:
            latest = session.execute(
                select(func.max(StockDaily.date)).where(StockDaily.code == code)
            ).scalar_one_or_none()
            return latest

    def get_latest_snapshots(self) -> List[StockDaily]:
        """Return the latest stored row for each stock code."""
        with self.db.get_session() as session:
            latest_dates = (
                select(
                    StockDaily.code.label("code"),
                    func.max(StockDaily.date).label("latest_date"),
                )
                .group_by(StockDaily.code)
                .subquery()
            )
            rows = session.execute(
                select(StockDaily)
                .join(
                    latest_dates,
                    and_(
                        StockDaily.code == latest_dates.c.code,
                        StockDaily.date == latest_dates.c.latest_date,
                    ),
                )
                .order_by(StockDaily.code)
            ).scalars().all()
            return list(rows)

    def get_latest_trade_dates(self, codes: List[str]) -> Dict[str, Optional[date]]:
        """Return latest stored trade date map for multiple stock codes."""
        normalized = [str(code).strip().upper() for code in codes if str(code).strip()]
        if not normalized:
            return {}

        with self.db.get_session() as session:
            rows = session.execute(
                select(
                    StockDaily.code,
                    func.max(StockDaily.date).label("latest_date"),
                )
                .where(StockDaily.code.in_(normalized))
                .group_by(StockDaily.code)
            ).all()

        result = {str(code).upper(): None for code in normalized}
        for code, latest_date in rows:
            result[str(code).upper()] = latest_date
        return result

    def get_range_for_all(
        self,
        start_date: date,
        end_date: date,
        limit_per_stock: int = 1
    ) -> List[StockDaily]:
        """
        Get daily data for all stocks in date range.

        Args:
            start_date: Start date
            end_date: End date
            limit_per_stock: Max records per stock (1 = latest only)

        Returns:
            List of StockDaily records
        """
        with self.db.get_session() as session:
            query = (
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.date >= start_date,
                        StockDaily.date <= end_date,
                    )
                )
                .order_by(desc(StockDaily.date))
            )
            # SQLite doesn't support window functions well, so we fetch all and limit in Python
            all_rows = session.execute(query).scalars().all()

            # Group by code and take first N per stock
            from collections import defaultdict
            grouped: Dict[str, List[StockDaily]] = defaultdict(list)
            for row in all_rows:
                grouped[row.code].append(row)

            result: List[StockDaily] = []
            for code, rows in grouped.items():
                result.extend(rows[:limit_per_stock])

            return result
