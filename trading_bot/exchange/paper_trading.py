"""
Paper Trading Provider - Demo/Simulation Mode
Simulates real trading with live market data but virtual money
"""

import time
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass, field

from trading_bot.core.interfaces import Exchange
from trading_bot.core.models import Position
from trading_bot.exchange.exness_web import ExnessWebProvider


@dataclass
class PaperPosition:
    """Paper trading position"""
    id: str
    symbol: str
    side: str
    entry_price: float
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    open_time: int = field(default_factory=lambda: int(time.time() * 1000))
    close_time: Optional[int] = None
    close_price: Optional[float] = None
    profit: float = 0.0
    status: str = "open"  # open, closed
    
    def calculate_profit(self, current_price: float, point_value: float = 0.01) -> float:
        """Calculate unrealized P&L"""
        if self.side == "long":
            pips = (current_price - self.entry_price) / point_value
        else:
            pips = (self.entry_price - current_price) / point_value
        
        # XAU/USD: 1 lot = 100 oz, 1 pip = $0.01
        contract_size = 100
        return pips * self.volume * contract_size * point_value


class PaperTradingProvider(Exchange):
    """
    Paper Trading Provider - Simulates trading with real market data
    
    Features:
    - Real-time price feed from Exness
    - Virtual balance tracking
    - Full position management
    - Trade history
    - Performance metrics
    """
    
    def __init__(
        self,
        data_provider: ExnessWebProvider,
        initial_balance: float = 10000.0,
        leverage: int = 200
    ):
        self.data_provider = data_provider
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.leverage = leverage
        self.margin_used = 0.0
        
        self.positions: List[PaperPosition] = []
        self.closed_positions: List[PaperPosition] = []
        self.position_counter = 0
        
        self.point_values = {
            "XAUUSDm": 0.01,
            "XAUUSD": 0.01,
            "BTCUSDm": 0.01,
            "EURUSDm": 0.0001,
        }
        
    def connect(self) -> bool:
        """Connect to data provider"""
        return self.data_provider.connect()
    
    def get_balance(self) -> float:
        """Get current balance"""
        return self.balance
    
    def get_equity(self) -> float:
        """Get current equity (balance + unrealized P&L)"""
        unrealized = sum(
            pos.calculate_profit(self._get_current_price(pos.symbol), self._get_point(pos.symbol))
            for pos in self.positions if pos.status == "open"
        )
        return self.balance + unrealized
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions"""
        positions = []
        for pos in self.positions:
            if pos.status != "open":
                continue
            if symbol and pos.symbol != symbol:
                continue
                
            current_price = self._get_current_price(pos.symbol)
            profit = pos.calculate_profit(current_price, self._get_point(pos.symbol))
            
            positions.append(Position(
                id=pos.id,
                symbol=pos.symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                volume=pos.volume,
                sl=pos.sl,
                tp=pos.tp,
                profit=profit,
                open_time=pos.open_time
            ))
        return positions
    
    def open_position(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        price: Optional[float] = None
    ) -> Optional[str]:
        """Open a paper position"""
        
        # Get entry price
        if price is None:
            price = self.data_provider.get_price(symbol)
        
        if price <= 0:
            print(f"❌ Invalid price for {symbol}")
            return None
        
        # Check margin
        margin_required = self._calculate_margin(symbol, volume, price)
        if margin_required > self.get_equity():
            print(f"❌ Insufficient margin. Required: ${margin_required:.2f}")
            return None
        
        # Create position
        self.position_counter += 1
        position = PaperPosition(
            id=str(self.position_counter),
            symbol=symbol,
            side=side,
            entry_price=price,
            volume=volume,
            sl=sl,
            tp=tp
        )
        
        self.positions.append(position)
        self.margin_used += margin_required
        
        entry_type = "BUY" if side == "long" else "SELL"
        print(f"✅ Paper {entry_type} {volume} lots {symbol} @ {price:.2f} [ID: {position.id}]")
        
        return position.id
    
    def close_position(self, position_id: str, symbol: Optional[str] = None) -> bool:
        """Close a paper position"""
        for pos in self.positions:
            if pos.id == position_id and pos.status == "open":
                current_price = self._get_current_price(pos.symbol)
                profit = pos.calculate_profit(current_price, self._get_point(pos.symbol))
                
                pos.status = "closed"
                pos.close_time = int(time.time() * 1000)
                pos.close_price = current_price
                pos.profit = profit
                
                self.balance += profit
                self.closed_positions.append(pos)
                
                # Return margin
                margin = self._calculate_margin(pos.symbol, pos.volume, pos.entry_price)
                self.margin_used -= margin
                
                print(f"✅ Closed #{position_id} @ {current_price:.2f} P&L: ${profit:+.2f}")
                return True
                
        return False
    
    def modify_position_sl(
        self,
        position_id: str,
        sl: float,
        tp: Optional[float] = None
    ) -> bool:
        """Modify position SL/TP"""
        for pos in self.positions:
            if pos.id == position_id and pos.status == "open":
                pos.sl = sl
                if tp is not None:
                    pos.tp = tp
                print(f"✅ Modified #{position_id} SL: {sl} TP: {tp}")
                return True
        return False
    
    def get_price(self, symbol: str) -> float:
        """Get current price"""
        return self.data_provider.get_price(symbol)
    
    def check_triggers(self):
        """Check SL/TP triggers for all positions"""
        for pos in list(self.positions):
            if pos.status != "open":
                continue
                
            current_price = self._get_current_price(pos.symbol)
            
            # Check SL
            if pos.sl:
                if pos.side == "long" and current_price <= pos.sl:
                    print(f"🔴 SL hit for #{pos.id} at {current_price:.2f}")
                    self.close_position(pos.id)
                elif pos.side == "short" and current_price >= pos.sl:
                    print(f"🔴 SL hit for #{pos.id} at {current_price:.2f}")
                    self.close_position(pos.id)
            
            # Check TP
            if pos.tp:
                if pos.side == "long" and current_price >= pos.tp:
                    print(f"🟢 TP hit for #{pos.id} at {current_price:.2f}")
                    self.close_position(pos.id)
                elif pos.side == "short" and current_price <= pos.tp:
                    print(f"🟢 TP hit for #{pos.id} at {current_price:.2f}")
                    self.close_position(pos.id)
    
    def get_stats(self) -> Dict:
        """Get trading statistics"""
        if not self.closed_positions:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "net_profit": 0
            }
        
        wins = [p for p in self.closed_positions if p.profit > 0]
        losses = [p for p in self.closed_positions if p.profit <= 0]
        
        total_profit = sum(p.profit for p in wins)
        total_loss = sum(abs(p.profit) for p in losses)
        
        return {
            "total_trades": len(self.closed_positions),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": len(wins) / len(self.closed_positions) * 100,
            "profit_factor": total_profit / total_loss if total_loss > 0 else float('inf'),
            "gross_profit": total_profit,
            "gross_loss": total_loss,
            "net_profit": sum(p.profit for p in self.closed_positions),
            "balance": self.balance,
            "equity": self.get_equity(),
            "open_positions": len([p for p in self.positions if p.status == "open"])
        }
    
    def print_report(self):
        """Print trading report"""
        stats = self.get_stats()
        
        print("\n" + "=" * 50)
        print("📊 PAPER TRADING REPORT")
        print("=" * 50)
        print(f"Balance:        ${stats['balance']:.2f}")
        print(f"Equity:         ${stats['equity']:.2f}")
        print(f"Open Positions: {stats['open_positions']}")
        print(f"Total Trades:   {stats['total_trades']}")
        if stats['total_trades'] > 0:
            print(f"Win Rate:       {stats['win_rate']:.1f}%")
            print(f"Profit Factor:  {stats['profit_factor']:.2f}")
            print(f"Net Profit:     ${stats['net_profit']:+.2f}")
        print("=" * 50)
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        return self.data_provider.get_price(symbol)
    
    def _get_point(self, symbol: str) -> float:
        """Get point value for symbol"""
        return self.point_values.get(symbol, 0.01)
    
    def _calculate_margin(self, symbol: str, volume: float, price: float) -> float:
        """Calculate required margin"""
        contract_size = 100  # XAU/USD
        return (volume * contract_size * price) / self.leverage
