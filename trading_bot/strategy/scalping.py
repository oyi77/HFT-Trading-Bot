"""
Scalping Strategy - Simple momentum-based scalping
Designed to work with any timeframe data
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from collections import deque

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class ScalpingConfig:
    """Configuration for Scalping Strategy"""

    lots: float = 0.01

    # Entry parameters
    lookback: int = 3  # Number of candles to check
    momentum_threshold: float = 0.001  # 0.1% price change

    # Exit parameters
    profit_target_pips: int = 10
    stop_loss_pips: int = 8

    # Point value for XAU
    point_value: float = 0.01

    # Max positions
    max_positions: int = 1

    # Trend filter
    use_ema_filter: bool = True
    ema_period: int = 20


class ScalpingStrategy(Strategy):
    """
    Simple momentum-based scalping strategy.
    Enter on momentum, exit on TP/SL.
    """

    def __init__(self, config: ScalpingConfig = None):
        if config is None:
            config = ScalpingConfig()
        super().__init__(config)

        self.prices: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        point = self.config.point_value

        # Store data
        self.prices.append(price)
        self.highs.append(ask)
        self.lows.append(bid)

        # Keep limited history
        if len(self.prices) > 50:
            self.prices = self.prices[-50:]
            self.highs = self.highs[-50:]
            self.lows = self.lows[-50:]

        # Need enough data
        if len(self.prices) < self.config.lookback + 2:
            return None

        # Check existing positions
        if positions:
            return self._manage_positions(positions, bid, ask, point)

        # Check position limit
        if len(positions) >= self.config.max_positions:
            return None

        # Analyze entry
        return self._analyze_entry(bid, ask, point)

    def _manage_positions(
        self, positions: List[Position], bid: float, ask: float, point: float
    ) -> Optional[Dict]:
        """Check TP/SL for existing positions"""

        for pos in positions:
            if pos.side == PositionSide.LONG:
                profit_pips = (bid - pos.entry_price) / point
                loss_pips = (pos.entry_price - ask) / point
            else:
                profit_pips = (pos.entry_price - ask) / point
                loss_pips = (bid - pos.entry_price) / point

            # Check TP
            if profit_pips >= self.config.profit_target_pips:
                return {"action": "close", "position_id": pos.id}

            # Check SL
            if loss_pips >= self.config.stop_loss_pips:
                return {"action": "close", "position_id": pos.id}

        return None

    def _analyze_entry(self, bid: float, ask: float, point: float) -> Optional[Dict]:
        """Analyze market for entry signals"""

        # Calculate momentum
        lookback = self.config.lookback
        recent = self.prices[-lookback:]

        if len(recent) < lookback:
            return None

        # Price change
        price_change = (recent[-1] - recent[0]) / recent[0]

        # Trend filter
        trend_ok = True
        if self.config.use_ema_filter and len(self.prices) >= self.config.ema_period:
            ema = sum(self.prices[-self.config.ema_period :]) / self.config.ema_period
            if recent[-1] < ema:
                trend_ok = False

        # Bullish signal
        if price_change > self.config.momentum_threshold and trend_ok:
            sl = bid - self.config.stop_loss_pips * point
            tp = ask + self.config.profit_target_pips * point

            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        # Bearish signal
        if price_change < -self.config.momentum_threshold and trend_ok:
            sl = ask + self.config.stop_loss_pips * point
            tp = bid - self.config.profit_target_pips * point

            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        return None

    def get_stats(self) -> Dict:
        return {
            "prices_collected": len(self.prices),
        }
