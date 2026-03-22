"""
Professional Backtest Engine with Full Metrics
Like MT5's Strategy Tester
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from trading_bot.exchange.base import Exchange
from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class Trade:
    """Single trade record"""
    entry_time: int
    exit_time: int
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    
    @property
    def duration_minutes(self) -> float:
        return (self.exit_time - self.entry_time) / 60000


@dataclass
class BacktestResult:
    """Complete backtest results"""
    # Basic stats
    start_date: str
    end_date: str
    initial_balance: float
    final_balance: float
    total_return: float
    total_return_pct: float
    
    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # P&L stats
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    avg_profit: float
    avg_loss: float
    avg_trade: float
    largest_profit: float
    largest_loss: float
    
    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    
    # Trade metrics
    avg_trade_duration: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    
    # Monthly returns
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    
    # Raw data
    equity_curve: List[tuple] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)


class BacktestEngine:
    """
    Professional Backtest Engine
    
    Features:
    - Tick-by-tick or bar-by-bar simulation
    - Realistic spread modeling
    - Slippage simulation
    - Commission calculation
    - Complete performance metrics
    - Equity curve tracking
    - Trade-by-trade analysis
    """
    
    def __init__(
        self,
        initial_balance: float = 10000,
        leverage: int = 200,
        spread: float = 0.02,  # For XAU/USD
        commission: float = 0,  # Per lot
        slippage: float = 0.01  # Price slippage
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.leverage = leverage
        self.spread = spread
        self.commission = commission
        self.slippage = slippage
        
        self.positions: List[Position] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[tuple] = []  # (timestamp, equity)
        
        self.peak_equity = initial_balance
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        
        self.point_value = 0.01  # XAU/USD
        self.contract_size = 100
        
    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        symbol: str = "XAUUSD",
        progress_callback: Optional[Callable] = None
    ) -> BacktestResult:
        """
        Run backtest
        
        Args:
            strategy: Strategy instance
            data: OHLCV dataframe
            symbol: Trading symbol
            progress_callback: Called with (current, total) for progress
        """
        print("🚀 Starting backtest...")
        
        # Reset state
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.positions = []
        self.closed_trades = []
        self.equity_curve = []
        self.peak_equity = self.initial_balance
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        
        total_rows = len(data)
        
        for i, row in data.iterrows():
            timestamp = int(row.get('timestamp', i))
            
            # Process bar
            self._process_bar(strategy, row, timestamp, symbol)
            
            # Record equity
            self._update_equity(timestamp)
            
            # Progress
            if progress_callback and i % 1000 == 0:
                progress_callback(i, total_rows)
                
        # Close all positions at end
        final_price = data.iloc[-1]['close']
        self._close_all_positions(final_price, data.iloc[-1].get('timestamp', 0))
        
        # Calculate results
        return self._calculate_results(data)
        
    def _process_bar(self, strategy: Strategy, row: pd.Series, timestamp: int, symbol: str):
        """Process single bar with OHLC walk simulation for realistic tick generation"""
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        
        # Simulate 4 ticks per bar: Open → High/Low → Low/High → Close
        # Direction depends on whether bar is bullish or bearish
        is_bullish = c >= o
        
        if is_bullish:
            # Bullish bar: O → L → H → C
            tick_prices = [o, l, h, c]
        else:
            # Bearish bar: O → H → L → C
            tick_prices = [o, h, l, c]
        
        for i, price in enumerate(tick_prices):
            sub_ts = timestamp + i  # Slight timestamp offset per sub-tick
            
            bid = price - self.spread / 2
            ask = price + self.spread / 2
            
            # Check SL/TP with the sub-tick high/low
            if i == 0:
                self._check_exits(h, l, sub_ts)
            
            # Get strategy signal
            signal = strategy.on_tick(price, bid, ask, self.positions, sub_ts)
            
            if signal:
                self._execute_signal(signal, symbol, ask, bid, sub_ts)
            
    def _execute_signal(
        self,
        signal: Dict,
        symbol: str,
        ask: float,
        bid: float,
        timestamp: int
    ):
        """Execute trading signal"""
        action = signal.get('action')
        
        if action == 'open':
            side = signal.get('side', 'long')
            volume = signal.get('amount', 0.01)
            sl = signal.get('sl')
            tp = signal.get('tp')
            
            entry_price = ask if side == 'long' else bid
            
            # Add slippage
            if side == 'long':
                entry_price += self.slippage
            else:
                entry_price -= self.slippage
                
            self._open_position(symbol, side, entry_price, volume, sl, tp, timestamp)
            
    def _open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        volume: float,
        sl: Optional[float],
        tp: Optional[float],
        timestamp: int
    ):
        """Open position"""
        # Deduct commission
        comm = volume * self.commission
        self.balance -= comm
        
        position = Position(
            id=str(len(self.positions) + len(self.closed_trades)),
            symbol=symbol,
            side=PositionSide.LONG if side in (OrderSide.BUY, 'buy', 'long') else PositionSide.SHORT,
            entry_price=entry_price,
            amount=volume,
            sl=sl,
            tp=tp,
            open_time=timestamp
        )
        
        self.positions.append(position)
        
    def _check_exits(self, high: float, low: float, timestamp: int):
        """Check SL/TP triggers"""
        for pos in list(self.positions):
            exit_price = None
            exit_reason = ""
            
            # Check SL
            if pos.sl:
                if pos.side == 'long' and low <= pos.sl:
                    exit_price = pos.sl
                    exit_reason = "SL"
                elif pos.side == 'short' and high >= pos.sl:
                    exit_price = pos.sl
                    exit_reason = "SL"
                    
            # Check TP
            if not exit_price and pos.tp:
                if pos.side == 'long' and high >= pos.tp:
                    exit_price = pos.tp
                    exit_reason = "TP"
                elif pos.side == 'short' and low <= pos.tp:
                    exit_price = pos.tp
                    exit_reason = "TP"
                    
            if exit_price:
                self._close_position(pos, exit_price, timestamp, exit_reason)
                
    def _close_position(
        self,
        position: Position,
        exit_price: float,
        timestamp: int,
        reason: str
    ):
        """Close position and record trade"""
        # Calculate P&L
        if position.side == PositionSide.LONG:
            pips = (exit_price - position.entry_price) / self.point_value
        else:
            pips = (position.entry_price - exit_price) / self.point_value
            
        pnl = pips * position.amount * self.contract_size * self.point_value
        
        # Deduct commission
        pnl -= position.amount * self.commission
        
        # Update balance
        self.balance += pnl
        
        # Record trade
        trade = Trade(
            entry_time=position.open_time,
            exit_time=timestamp,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            volume=position.amount,
            sl=position.sl,
            tp=position.tp,
            pnl=pnl,
            pnl_pct=(pnl / self.initial_balance) * 100,
            exit_reason=reason
        )
        
        self.closed_trades.append(trade)
        self.positions.remove(position)
        
    def _close_all_positions(self, final_price: float, timestamp: int):
        """Close all positions at end of backtest"""
        for pos in list(self.positions):
            self._close_position(pos, final_price, timestamp, "END")
            
    def _update_equity(self, timestamp: int):
        """Update equity curve"""
        # Calculate unrealized P&L
        unrealized = sum(p.unrealized_pnl for p in self.positions)
        self.equity = self.balance + unrealized
        
        # Update peak and drawdown
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
            
        drawdown = self.peak_equity - self.equity
        drawdown_pct = (drawdown / self.peak_equity) * 100
        
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            self.max_drawdown_pct = drawdown_pct
            
        self.equity_curve.append((timestamp, self.equity))
        
    def _calculate_results(self, data: pd.DataFrame) -> BacktestResult:
        """Calculate comprehensive backtest results"""
        trades = self.closed_trades
        
        if not trades:
            print("⚠️ No trades executed during backtest")
            return BacktestResult(
                start_date="", end_date="", initial_balance=self.initial_balance,
                final_balance=self.balance, total_return=0, total_return_pct=0,
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0,
                gross_profit=0, gross_loss=0, net_profit=0, profit_factor=0,
                avg_profit=0, avg_loss=0, avg_trade=0, largest_profit=0,
                largest_loss=0, max_drawdown=0, max_drawdown_pct=0,
                sharpe_ratio=0, sortino_ratio=0, avg_trade_duration=0,
                max_consecutive_wins=0, max_consecutive_losses=0
            )
        
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = sum(abs(t.pnl) for t in losses)
        
        # Calculate consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.pnl_pct for t in trades]
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if returns else 1
        sharpe = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        
        # Sortino ratio (downside deviation only)
        downside_returns = [r for r in returns if r < 0]
        downside_std = np.std(downside_returns) if downside_returns else 1
        sortino = (avg_return / downside_std) * np.sqrt(252) if downside_std > 0 else 0
        
        # Monthly returns
        monthly_returns = {}
        
        return BacktestResult(
            start_date=datetime.fromtimestamp(trades[0].entry_time / 1000).strftime('%Y-%m-%d'),
            end_date=datetime.fromtimestamp(trades[-1].exit_time / 1000).strftime('%Y-%m-%d'),
            initial_balance=self.initial_balance,
            final_balance=self.balance,
            total_return=self.balance - self.initial_balance,
            total_return_pct=((self.balance - self.initial_balance) / self.initial_balance) * 100,
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=(len(wins) / len(trades) * 100) if trades else 0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=gross_profit - gross_loss,
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            avg_profit=gross_profit / len(wins) if wins else 0,
            avg_loss=gross_loss / len(losses) if losses else 0,
            avg_trade=sum(t.pnl for t in trades) / len(trades) if trades else 0,
            largest_profit=max(t.pnl for t in wins) if wins else 0,
            largest_loss=min(t.pnl for t in losses) if losses else 0,
            max_drawdown=self.max_drawdown,
            max_drawdown_pct=self.max_drawdown_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            avg_trade_duration=np.mean([t.duration_minutes for t in trades]) if trades else 0,
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            monthly_returns=monthly_returns,
            equity_curve=self.equity_curve,
            trades=trades
        )
        
    def print_report(self, result: BacktestResult):
        """Print formatted backtest report"""
        print("\n" + "=" * 60)
        print("📊 BACKTEST REPORT")
        print("=" * 60)
        print(f"Period:           {result.start_date} to {result.end_date}")
        print(f"Initial Balance:  ${result.initial_balance:,.2f}")
        print(f"Final Balance:    ${result.final_balance:,.2f}")
        print(f"Total Return:     ${result.total_return:,.2f} ({result.total_return_pct:+.2f}%)")
        print("-" * 60)
        print("TRADE STATISTICS:")
        print(f"  Total Trades:   {result.total_trades}")
        print(f"  Win Rate:       {result.win_rate:.1f}% ({result.winning_trades}/{result.losing_trades})")
        print(f"  Profit Factor:  {result.profit_factor:.2f}")
        print(f"  Sharpe Ratio:   {result.sharpe_ratio:.2f}")
        print("-" * 60)
        print("P&L STATISTICS:")
        print(f"  Gross Profit:   ${result.gross_profit:,.2f}")
        print(f"  Gross Loss:     ${result.gross_loss:,.2f}")
        print(f"  Net Profit:     ${result.net_profit:,.2f}")
        print(f"  Avg Profit:     ${result.avg_profit:,.2f}")
        print(f"  Avg Loss:       ${result.avg_loss:,.2f}")
        print("-" * 60)
        print("RISK METRICS:")
        print(f"  Max Drawdown:   ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
        print(f"  Sortino Ratio:  {result.sortino_ratio:.2f}")
        print("=" * 60)
        
    def save_report(self, result: BacktestResult, filepath: str):
        """Save report to JSON"""
        data = {
            'summary': {
                'start_date': result.start_date,
                'end_date': result.end_date,
                'initial_balance': result.initial_balance,
                'final_balance': result.final_balance,
                'total_return': result.total_return,
                'total_return_pct': result.total_return_pct,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown': result.max_drawdown,
                'max_drawdown_pct': result.max_drawdown_pct
            },
            'trades': [
                {
                    'entry_time': t.entry_time,
                    'exit_time': t.exit_time,
                    'symbol': t.symbol,
                    'side': t.side,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'exit_reason': t.exit_reason
                }
                for t in result.trades
            ]
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"💾 Report saved to {filepath}")
