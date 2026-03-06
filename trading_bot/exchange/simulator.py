"""
Standalone Trading Simulator - No broker connection required
Pure simulation with generated or historical data
"""

import random
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SimulatedPosition:
    """Simulated trading position"""

    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    open_time: float = field(default_factory=time.time)
    close_time: Optional[float] = None
    close_price: Optional[float] = None
    profit: float = 0.0
    status: str = "open"

    # Alias for compatibility with Position model
    @property
    def amount(self) -> float:
        return self.volume

    def calculate_profit(
        self, current_price: float, point_value: float = 0.01
    ) -> float:
        """Calculate unrealized P&L"""
        if self.side == "buy":
            pips = (current_price - self.entry_price) / point_value
        else:
            pips = (self.entry_price - current_price) / point_value

        # XAU/USD: volume * 100 oz * $0.01 per pip
        contract_size = 100
        return pips * self.volume * contract_size * point_value


class SimulatorExchange:
    """
    Standalone simulator - no broker connection needed
    Uses simulated price data for pure backtesting/paper trading
    """

    def __init__(self, initial_balance: float = 100.0, symbol: str = "XAUUSDm"):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.symbol = symbol

        self.positions: List[SimulatedPosition] = []
        self.closed_positions: List[SimulatedPosition] = []
        self.trades: List[Dict] = []
        self.position_counter = 0

        # Current simulated price
        self.current_price = 5000.0
        self.price_history: List[float] = []

        # Simulation parameters
        self.volatility = 0.5  # Price movement volatility
        self.trend = 0.0  # Price trend bias

    def get_price(self) -> float:
        """Get current simulated price"""
        return self.current_price

    def get_balance(self) -> float:
        """Get current balance"""
        return self.balance

    def get_equity(self) -> float:
        """Get equity (balance + unrealized P&L)"""
        unrealized = sum(
            pos.calculate_profit(self.current_price)
            for pos in self.positions
            if pos.status == "open"
        )
        return self.balance + unrealized

    def get_positions(self, symbol: str = None) -> List[SimulatedPosition]:
        """Get open positions"""
        return [p for p in self.positions if p.status == "open"]

    def open_position(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> Optional[str]:
        """Open a simulated position"""
        self.position_counter += 1

        # Use current price with small spread
        spread = 0.04
        if side == "buy":
            entry_price = self.current_price + spread / 2
        else:
            entry_price = self.current_price - spread / 2

        position = SimulatedPosition(
            id=str(self.position_counter),
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            volume=volume,
            sl=sl,
            tp=tp,
        )

        self.positions.append(position)

        self.trades.append(
            {
                "time": datetime.now().isoformat(),
                "action": "open",
                "side": side,
                "symbol": symbol,
                "volume": volume,
                "price": entry_price,
            }
        )

        return position.id

    def close_position(self, position_id: str) -> bool:
        """Close a position by ID"""
        for pos in self.positions:
            if pos.id == position_id and pos.status == "open":
                # Calculate profit
                profit = pos.calculate_profit(self.current_price)

                pos.status = "closed"
                pos.close_time = time.time()
                pos.close_price = self.current_price
                pos.profit = profit

                self.balance += profit
                self.closed_positions.append(pos)

                self.trades.append(
                    {
                        "time": datetime.now().isoformat(),
                        "action": "close",
                        "position_id": position_id,
                        "price": self.current_price,
                        "profit": profit,
                    }
                )

                return True

        return False

    def modify_position(
        self, position_id: str, sl: float = None, tp: float = None
    ) -> bool:
        """Modify position SL/TP"""
        for pos in self.positions:
            if pos.id == position_id and pos.status == "open":
                if sl is not None:
                    pos.sl = sl
                if tp is not None:
                    pos.tp = tp
                return True
        return False

    def update_price(self, new_price: Optional[float] = None):
        """
        Update simulated price
        If new_price not provided, generates random walk
        """
        if new_price is not None:
            self.current_price = new_price
        else:
            # Random walk with trend
            change = random.gauss(self.trend, self.volatility)
            self.current_price += change

            # Keep price positive
            self.current_price = max(1.0, self.current_price)

        self.price_history.append(self.current_price)

        # Check SL/TP
        self._check_triggers()

    def _check_triggers(self):
        """Check and execute SL/TP"""
        for pos in list(self.positions):
            if pos.status != "open":
                continue

            # Check SL
            if pos.sl:
                if pos.side == "buy" and self.current_price <= pos.sl:
                    self.close_position(pos.id)
                elif pos.side == "sell" and self.current_price >= pos.sl:
                    self.close_position(pos.id)

            # Check TP
            if pos.tp:
                if pos.side == "buy" and self.current_price >= pos.tp:
                    self.close_position(pos.id)
                elif pos.side == "sell" and self.current_price <= pos.tp:
                    self.close_position(pos.id)

    def update_positions(self, current_price: float):
        """Update positions with new price"""
        self.current_price = current_price
        self._check_triggers()

    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics"""
        if not self.closed_positions:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "net_pnl": 0.0,
                "balance": self.balance,
                "equity": self.get_equity(),
            }

        wins = [p for p in self.closed_positions if p.profit > 0]
        losses = [p for p in self.closed_positions if p.profit <= 0]

        total_profit = sum(p.profit for p in wins)
        total_loss = sum(abs(p.profit) for p in losses)
        net_pnl = sum(p.profit for p in self.closed_positions)

        return {
            "total_trades": len(self.closed_positions),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": (len(wins) / len(self.closed_positions) * 100)
            if self.closed_positions
            else 0,
            "total_profit": total_profit,
            "total_loss": total_loss,
            "net_pnl": net_pnl,
            "balance": self.balance,
            "equity": self.get_equity(),
            "open_positions": len([p for p in self.positions if p.status == "open"]),
        }

    def close(self):
        return None

    def print_report(self):
        """Print trading report"""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("📊 SIMULATION REPORT")
        print("=" * 60)
        print(f"Initial Balance: ${self.initial_balance:.2f}")
        print(f"Final Balance:   ${stats['balance']:.2f}")
        print(f"Final Equity:    ${stats['equity']:.2f}")
        print(f"Net P&L:         ${stats['net_pnl']:+.2f}")
        print("-" * 60)
        print(f"Total Trades:    {stats['total_trades']}")
        print(f"Winning:         {stats['winning_trades']}")
        print(f"Losing:          {stats['losing_trades']}")
        if stats["total_trades"] > 0:
            print(f"Win Rate:        {stats['win_rate']:.1f}%")
            print(
                f"Profit Factor:   {stats['total_profit'] / stats['total_loss']:.2f}"
                if stats["total_loss"] > 0
                else "∞"
            )
        print("=" * 60)
