"""
Momentum Grid Strategy - Combines momentum with grid-like entries
Based on working Grid pattern
"""

from typing import Dict, Optional, List
from dataclasses import dataclass

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class MomentumGridConfig:
    lots: float = 0.01
    grid_spacing_pct: float = 0.005
    grid_levels: int = 5
    max_total_positions: int = 5
    momentum_lookback: int = 3
    momentum_threshold: float = 0.002
    point_value: float = 0.01


class MomentumGridStrategy(Strategy):
    def __init__(self, config: MomentumGridConfig = None):
        if config is None:
            config = MomentumGridConfig()
        super().__init__(config)

        self.prices: List[float] = []
        self.base_price = None

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        point = self.config.point_value

        # Store price
        self.prices.append(price)
        if len(self.prices) > 50:
            self.prices = self.prices[-50:]

        # Initialize base price
        if self.base_price is None:
            self.base_price = price
            return None

        # Update base price
        self.base_price = self.base_price * 0.999 + price * 0.001

        # Check position limit
        if len(positions) >= self.config.max_total_positions:
            return None

        # Close profitable positions
        for pos in positions:
            if pos.tp:
                if pos.side == PositionSide.LONG and price >= pos.tp:
                    return {"action": "close", "position_id": pos.id}
                elif pos.side == PositionSide.SHORT and price <= pos.tp:
                    return {"action": "close", "position_id": pos.id}

        # Calculate momentum
        if len(self.prices) >= self.config.momentum_lookback + 1:
            lookback = self.config.momentum_lookback
            momentum = (self.prices[-1] - self.prices[-lookback - 1]) / self.prices[
                -lookback - 1
            ]
        else:
            return None

        # Grid size
        grid_size = self.base_price * self.config.grid_spacing_pct

        # Long entry on momentum dip
        if momentum > self.config.momentum_threshold:
            buy_level = self.base_price - grid_size
            if price < buy_level:
                sl = price - grid_size * 2
                tp = self.base_price

                # Check for nearby positions
                for pos in positions:
                    if (
                        pos.side == PositionSide.LONG
                        and abs(pos.entry_price - price) < grid_size * 0.5
                    ):
                        return None

                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        # Short entry on momentum rally
        if momentum < -self.config.momentum_threshold:
            sell_level = self.base_price + grid_size
            if price > sell_level:
                sl = price + grid_size * 2
                tp = self.base_price

                for pos in positions:
                    if (
                        pos.side == PositionSide.SHORT
                        and abs(pos.entry_price - price) < grid_size * 0.5
                    ):
                        return None

                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        return None
