# -*- coding: utf-8 -*-
"""
===================================
Built-in Backtest Engine
===================================

A lightweight but powerful backtesting engine for evaluating trading strategies.

Features:
1. Simple buy/sell signal simulation
2. Calculate key metrics: win rate, returns, Sharpe ratio, max drawdown
3. Support for profit targets and stop losses
4. Generate detailed backtest reports
5. Trade-by-trade analysis

Usage:
    engine = StrategyBacktestEngine(initial_capital=100000.0)
    result = engine.run_backtest(
        data=stock_data,
        entry_signal=buy_signals,
        exit_signal=sell_signals,
        profit_target=0.10,  # 10% take profit
        stop_loss=-0.05      # 5% stop loss
    )
    engine.print_report(result)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade."""
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: float
    profit: float
    profit_pct: float
    
    def __str__(self):
        return (f"Trade: {self.entry_date} -> {self.exit_date}, "
                f"Entry: {self.entry_price:.2f}, Exit: {self.exit_price:.2f}, "
                f"Profit: {self.profit:.2f} ({self.profit_pct:.2%})")


@dataclass
class BacktestResult:
    """Contains comprehensive backtest results."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_profit: float
    avg_win: float
    avg_loss: float
    avg_profit_pct: float
    total_profit: float
    total_profit_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_profit': self.avg_profit,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'avg_profit_pct': self.avg_profit_pct,
            'total_profit': self.total_profit,
            'total_profit_pct': self.total_profit_pct,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'sharpe_ratio': self.sharpe_ratio,
        }


class StrategyBacktestEngine:
    """
    Backtesting engine for evaluating trading strategies.
    
    This engine simulates trading based on entry and exit signals,
    calculating performance metrics and generating detailed reports.
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        Initialize the backtest engine.
        
        Args:
            initial_capital: Starting capital for backtesting (default: 100000.0)
        """
        self.initial_capital = initial_capital
        logger.info(f"StrategyBacktestEngine initialized with capital: {initial_capital:.2f}")
    
    def run_backtest(
        self,
        data: pd.DataFrame,
        entry_signal: pd.Series,
        exit_signal: pd.Series,
        profit_target: Optional[float] = None,
        stop_loss: Optional[float] = None,
        commission: float = 0.001,  # 0.1% commission per trade
        slippage: float = 0.001,     # 0.1% slippage per trade
    ) -> BacktestResult:
        """
        Run backtest on provided data and signals.
        
        Args:
            data: Stock data DataFrame (must contain date, open, high, low, close)
            entry_signal: Boolean Series where True indicates buy signal
            exit_signal: Boolean Series where True indicates sell signal
            profit_target: Take profit target (e.g., 0.10 for 10%)
            stop_loss: Stop loss level (e.g., -0.05 for -5%)
            commission: Commission rate per trade (default: 0.1%)
            slippage: Slippage rate per trade (default: 0.1%)
            
        Returns:
            BacktestResult object with detailed statistics
        """
        # Validate input
        self._validate_input(data, entry_signal, exit_signal)
        
        # Prepare data
        data = data.copy()
        data['date'] = pd.to_datetime(data['date'])
        data = data.sort_values('date').reset_index(drop=True)
        
        trades = []
        position = None  # (entry_date, entry_price, shares)
        capital = self.initial_capital
        equity_curve = [capital]
        
        logger.info(f"Starting backtest with {len(data)} data points")
        
        for i in range(len(data)):
            row = data.iloc[i]
            
            # Check if we need to take profit or stop loss
            if position is not None:
                entry_date, entry_price, shares = position
                current_price = row['close']
                profit_pct = (current_price - entry_price) / entry_price
                
                # Take profit
                if profit_target is not None and profit_pct >= profit_target:
                    exit_date = row['date']
                    exit_price = current_price * (1 - slippage)  # Slippage on exit
                    profit = shares * (exit_price - entry_price) - shares * entry_price * commission
                    profit_pct = (exit_price - entry_price) / entry_price - commission
                    
                    trades.append(Trade(
                        entry_date=str(entry_date.date()),
                        entry_price=entry_price,
                        exit_date=str(exit_date.date()),
                        exit_price=exit_price,
                        shares=shares,
                        profit=profit,
                        profit_pct=profit_pct
                    ))
                    position = None
                    capital += profit
                    equity_curve.append(capital)
                    logger.debug(f"Take profit: {profit_pct:.2%}")
                
                # Stop loss
                elif stop_loss is not None and profit_pct <= stop_loss:
                    exit_date = row['date']
                    exit_price = current_price * (1 - slippage)  # Slippage on exit
                    profit = shares * (exit_price - entry_price) - shares * entry_price * commission
                    profit_pct = (exit_price - entry_price) / entry_price - commission
                    
                    trades.append(Trade(
                        entry_date=str(entry_date.date()),
                        entry_price=entry_price,
                        exit_date=str(exit_date.date()),
                        exit_price=exit_price,
                        shares=shares,
                        profit=profit,
                        profit_pct=profit_pct
                    ))
                    position = None
                    capital += profit
                    equity_curve.append(capital)
                    logger.debug(f"Stop loss: {profit_pct:.2%}")
            
            # Entry signal (buy)
            if position is None and entry_signal.iloc[i] and i < len(data) - 1:
                entry_price = data.iloc[i + 1]['open'] * (1 + slippage)  # Next day open + slippage
                shares = capital / entry_price
                position = (row['date'], entry_price, shares)
                logger.debug(f"Entry: {row['date'].date()} @ {entry_price:.2f}")
            
            # Exit signal (sell) - if not already exited by take profit/stop loss
            elif position is not None and exit_signal.iloc[i]:
                entry_date, entry_price, shares = position
                exit_price = row['open'] * (1 - slippage)  # Slippage on exit
                profit = shares * (exit_price - entry_price) - shares * entry_price * commission
                profit_pct = (exit_price - entry_price) / entry_price - commission
                
                trades.append(Trade(
                    entry_date=str(entry_date.date()),
                    entry_price=entry_price,
                    exit_date=str(row['date'].date()),
                    exit_price=exit_price,
                    shares=shares,
                    profit=profit,
                    profit_pct=profit_pct
                ))
                position = None
                capital += profit
                equity_curve.append(capital)
                logger.debug(f"Exit: {row['date'].date()} @ {exit_price:.2f}")
        
        # Calculate statistics
        result = self._calculate_stats(trades, equity_curve)
        logger.info(f"Backtest completed: {result.total_trades} trades, "
                   f"win rate: {result.win_rate:.2%}")
        
        return result
    
    def _validate_input(
        self,
        data: pd.DataFrame,
        entry_signal: pd.Series,
        exit_signal: pd.Series
    ) -> None:
        """Validate input data and signals."""
        required_columns = ['date', 'open', 'high', 'low', 'close']
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"Data must contain column: {col}")
        
        if len(entry_signal) != len(data):
            raise ValueError("Entry signal length must match data length")
        
        if len(exit_signal) != len(data):
            raise ValueError("Exit signal length must match data length")
    
    def _calculate_stats(
        self,
        trades: List[Trade],
        equity_curve: List[float]
    ) -> BacktestResult:
        """Calculate backtest statistics."""
        if not trades:
            return BacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_profit=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                avg_profit_pct=0.0,
                total_profit=0.0,
                total_profit_pct=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                trades=[],
                equity_curve=equity_curve
            )
        
        # Separate winning and losing trades
        winning_trades = [t for t in trades if t.profit > 0]
        losing_trades = [t for t in trades if t.profit <= 0]
        
        total_trades = len(trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Profit statistics
        total_profit = sum(t.profit for t in trades)
        total_profit_pct = (total_profit / self.initial_capital) * 100
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        avg_profit_pct = avg_profit / (self.initial_capital / total_trades) if total_trades > 0 else 0
        
        avg_win = np.mean([t.profit for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.profit for t in losing_trades]) if losing_trades else 0
        
        # Maximum drawdown
        if len(equity_curve) > 1:
            equity_array = np.array(equity_curve)
            running_max = np.maximum.accumulate(equity_array)
            drawdown = (running_max - equity_array) / running_max
            max_drawdown_pct = drawdown.max() if len(drawdown) > 0 else 0
            max_drawdown = max_drawdown_pct * self.initial_capital
        else:
            max_drawdown_pct = 0
            max_drawdown = 0
        
        # Sharpe ratio (annualized, simplified)
        returns = [t.profit_pct for t in trades]
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_profit_pct=avg_profit_pct,
            total_profit=total_profit,
            total_profit_pct=total_profit_pct,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            equity_curve=equity_curve
        )
    
    def print_report(self, result: BacktestResult) -> None:
        """Print a detailed backtest report."""
        print("\n" + "=" * 60)
        print(" " * 15 + "BACKTEST REPORT")
        print("=" * 60)
        print(f"\n📊 TRADE STATISTICS")
        print("-" * 60)
        print(f"  Total Trades:        {result.total_trades}")
        print(f"  Winning Trades:      {result.winning_trades}")
        print(f"  Losing Trades:       {result.losing_trades}")
        print(f"  Win Rate:            {result.win_rate:.2%}")
        
        print(f"\n💰 PROFITABILITY")
        print("-" * 60)
        print(f"  Total Profit:        {result.total_profit:,.2f}")
        print(f"  Total Return:        {result.total_profit_pct:.2f}%")
        print(f"  Avg Profit/Trade:    {result.avg_profit:,.2f}")
        print(f"  Avg Win:             {result.avg_win:,.2f}")
        print(f"  Avg Loss:            {result.avg_loss:,.2f}")
        print(f"  Avg Profit %:        {result.avg_profit_pct:.2f}%")
        
        print(f"\n📉 RISK METRICS")
        print("-" * 60)
        print(f"  Max Drawdown:        {result.max_drawdown:,.2f}")
        print(f"  Max Drawdown %:      {result.max_drawdown_pct:.2%}")
        print(f"  Sharpe Ratio:        {result.sharpe_ratio:.2f}")
        
        print(f"\n🎯 INITIAL CAPITAL:    {self.initial_capital:,.2f}")
        print(f"   FINAL CAPITAL:      {self.initial_capital + result.total_profit:,.2f}")
        print("=" * 60 + "\n")
        
        # Log to logger as well
        logger.info(
            f"Backtest Report: {result.total_trades} trades, "
            f"win_rate={result.win_rate:.2%}, "
            f"return={result.total_profit_pct:.2f}%, "
            f"sharpe={result.sharpe_ratio:.2f}"
        )
    
    def get_trade_list(self, result: BacktestResult) -> pd.DataFrame:
        """
        Get trades as a DataFrame for analysis.
        
        Args:
            result: BacktestResult from run_backtest
            
        Returns:
            DataFrame with trade details
        """
        if not result.trades:
            return pd.DataFrame()
        
        data = []
        for i, trade in enumerate(result.trades, 1):
            data.append({
                'trade_id': i,
                'entry_date': trade.entry_date,
                'entry_price': trade.entry_price,
                'exit_date': trade.exit_date,
                'exit_price': trade.exit_price,
                'shares': trade.shares,
                'profit': trade.profit,
                'profit_pct': trade.profit_pct,
                'result': 'WIN' if trade.profit > 0 else 'LOSS'
            })
        
        return pd.DataFrame(data)
    
    def compare_strategies(
        self,
        results: List[Tuple[str, BacktestResult]]
    ) -> pd.DataFrame:
        """
        Compare multiple backtest results.
        
        Args:
            results: List of (strategy_name, BacktestResult) tuples
            
        Returns:
            DataFrame with comparison
        """
        comparison = []
        for name, result in results:
            comparison.append({
                'Strategy': name,
                'Total Trades': result.total_trades,
                'Win Rate': f"{result.win_rate:.2%}",
                'Total Return': f"{result.total_profit_pct:.2f}%",
                'Avg Profit': f"{result.avg_profit:.2f}",
                'Max Drawdown': f"{result.max_drawdown_pct:.2%}",
                'Sharpe Ratio': f"{result.sharpe_ratio:.2f}"
            })
        
        return pd.DataFrame(comparison)


def create_ma_signals(data: pd.DataFrame, short_period: int = 5, long_period: int = 20):
    """
    Create simple moving average crossover signals.
    
    Args:
        data: Stock data DataFrame
        short_period: Short MA period (default: 5)
        long_period: Long MA period (default: 20)
        
    Returns:
        Tuple of (entry_signal, exit_signal) Series
    """
    data = data.copy()
    data['ma_short'] = data['close'].rolling(window=short_period).mean()
    data['ma_long'] = data['close'].rolling(window=long_period).mean()
    
    # Golden cross: short MA crosses above long MA
    data['golden_cross'] = (
        (data['ma_short'] > data['ma_long']) &
        (data['ma_short'].shift(1) <= data['ma_long'].shift(1))
    )
    
    # Death cross: short MA crosses below long MA
    data['death_cross'] = (
        (data['ma_short'] < data['ma_long']) &
        (data['ma_short'].shift(1) >= data['ma_long'].shift(1))
    )
    
    return data['golden_cross'], data['death_cross']


# Backward-compatible alias during migration.
BacktestEngine = StrategyBacktestEngine
