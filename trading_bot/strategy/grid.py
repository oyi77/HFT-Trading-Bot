"""
Grid Strategy - Mean reversion grid trading
Good for ranging markets like XAU during certain periods
"""

from typing import Dict, Optional, List, Deque
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class GridConfig:
    """Configuration for Grid Strategy"""

    lots: float = 0.01
    grid_levels: int = 5
    grid_spacing_pct: float = 0.005  # 0.5% spacing
    max_total_positions: int = 10
    max_daily_loss: float = 50.0
    drawdown_limit_pct: float = 5.0  # Stop trading if drawdown exceeds this
    use_atr_sizing: bool = False
    atr_tp_multiplier: float = 1.5


class GridStrategy(Strategy):
    """
    Grid trading strategy with risk management.
    Places buy orders at lower prices, sell orders at higher prices.
    Includes drawdown protection and position limits.
    """

    def __init__(self, config: GridConfig = None):
        if config is None:
            config = GridConfig()
        super().__init__(config)

        self.base_price = None
        self.initial_equity = None
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.peak_equity = 0.0

        # Track grid levels
        self.active_buy_levels = deque(maxlen=20)
        self.active_sell_levels = deque(maxlen=20)

        # Session tracking
        self.session_start = datetime.now()

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
        equity: float = None,
    ) -> Optional[Dict]:
        # Initialize equity tracking
        if self.initial_equity is None and equity:
            self.initial_equity = equity
            self.peak_equity = equity

        # Update peak equity
        if equity and equity > self.peak_equity:
            self.peak_equity = equity

        # Check drawdown limit
        if self._check_drawdown_limit(equity):
            return None

        # Check daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss:
            return None

        # Initialize base price
        if self.base_price is None:
            self.base_price = price
            return None

        # Update base price slowly (trailing center)
        self.base_price = self.base_price * 0.999 + price * 0.001

        # Count positions by side
        longs = [p for p in positions if p.side == PositionSide.LONG]
        shorts = [p for p in positions if p.side == PositionSide.SHORT]
        total_positions = len(positions)

        # Calculate grid size
        grid_size = self.base_price * self.config.grid_spacing_pct

        # Close profitable positions first
        for pos in positions:
            if pos.tp and pos.tp > 0:
                if pos.side == PositionSide.LONG and price >= pos.tp:
                    self._record_trade(pos.entry_price, pos.tp, True)
                    return {"action": "close", "position_id": pos.id}
                elif pos.side == PositionSide.SHORT and price <= pos.tp:
                    self._record_trade(pos.entry_price, pos.tp, False)
                    return {"action": "close", "position_id": pos.id}

        # Check position limits
        if total_positions >= self.config.max_total_positions:
            return None

        # Check if we should open long (price is below grid level)
        buy_level = self.base_price - grid_size
        if price < buy_level and len(longs) < self.config.grid_levels:
            # Calculate SL and TP
            sl = price - grid_size * 2
            tp = self.base_price  # TP at center

            # Check if this level already has a position nearby
            if not self._has_nearby_level(longs, price, grid_size * 0.5):
                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        # Check if we should open short (price is above grid level)
        sell_level = self.base_price + grid_size
        if price > sell_level and len(shorts) < self.config.grid_levels:
            # Calculate SL and TP
            sl = price + grid_size * 2
            tp = self.base_price  # TP at center

            # Check if this level already has a position nearby
            if not self._has_nearby_level(shorts, price, grid_size * 0.5):
                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        return None

    def _check_drawdown_limit(self, equity: float) -> bool:
        """Check if drawdown exceeds limit."""
        if not equity or not self.peak_equity or self.peak_equity == 0:
            return False

        drawdown_pct = ((self.peak_equity - equity) / self.peak_equity) * 100
        return drawdown_pct >= self.config.drawdown_limit_pct

    def _has_nearby_level(
        self, positions: List[Position], price: float, threshold: float
    ) -> bool:
        """Check if there's already a position near this price level."""
        for pos in positions:
            if abs(pos.entry_price - price) < threshold:
                return True
        return False

    def _record_trade(self, entry: float, exit_price: float, is_long: bool):
        """Record trade result."""
        self.trades_today += 1
        if is_long:
            profit = exit_price - entry
        else:
            profit = entry - exit_price

        pip_value = self.config.lots * 10
        self.daily_pnl += profit * pip_value

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "base_price": round(self.base_price, 2) if self.base_price else 0,
            "trades_today": self.trades_today,
            "daily_pnl": round(self.daily_pnl, 2),
            "peak_equity": round(self.peak_equity, 2) if self.peak_equity else 0,
        }
