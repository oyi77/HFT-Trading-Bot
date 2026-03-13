"""
Trend Following Strategy - EMA Crossover with RSI filter
"""

from typing import Dict, Optional, List
from dataclasses import dataclass

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide
from trading_bot.utils.indicators import calculate_ema, calculate_rsi, calculate_atr


@dataclass
class TrendConfig:
    """Configuration for Trend Strategy"""

    lots: float = 0.01
    ema_fast: int = 9
    ema_slow: int = 21
    stop_loss_pips: int = 30
    take_profit_pips: int = 75
    use_rsi_filter: bool = True
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    use_atr_sizing: bool = True
    atr_period: int = 14
    atr_sl_multiplier: float = 1.5
    atr_tp_multiplier: float = 2.5
    point_value: float = 0.01


class TrendStrategy(Strategy):
    """
    EMA crossover trend strategy with RSI filter.
    Enters on trend changes when RSI confirms.
    Uses ATR-based or fixed TP/SL.
    """

    def __init__(self, config: TrendConfig = None):
        if config is None:
            config = TrendConfig()
        super().__init__(config)

        self.prices: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []
        self.trend = None  # 'up' or 'down'

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        mid_price = (bid + ask) / 2
        self.prices.append(mid_price)
        self.highs.append(ask)
        self.lows.append(bid)

        # Need enough data
        min_bars = max(self.config.ema_slow, self.config.rsi_period) + 5
        if len(self.prices) < min_bars:
            return None

        # Calculate indicators
        fast_ema = calculate_ema(self.prices, self.config.ema_fast)
        slow_ema = calculate_ema(self.prices, self.config.ema_slow)
        rsi = (
            calculate_rsi(self.prices, self.config.rsi_period)
            if self.config.use_rsi_filter
            else None
        )

        if fast_ema is None or slow_ema is None:
            return None

        # Determine trend
        prev_trend = self.trend
        self.trend = "up" if fast_ema > slow_ema else "down"

        # No trend change
        if prev_trend == self.trend:
            return None

        # Close opposite positions on trend change
        for pos in positions:
            if (self.trend == "up" and pos.side == PositionSide.SHORT) or (
                self.trend == "down" and pos.side == PositionSide.LONG
            ):
                return {"action": "close", "position_id": pos.id}

        # Enter new position
        point = self.config.point_value

        if self.trend == "up" and not any(
            p.side == PositionSide.LONG for p in positions
        ):
            # RSI filter - don't buy if overbought
            if rsi is not None and rsi > self.config.rsi_overbought:
                return None

            sl, tp = self._calculate_sl_tp(bid, ask, True)

            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": self.config.lots,
                "sl": sl,
                "tp": tp,
            }

        if self.trend == "down" and not any(
            p.side == PositionSide.SHORT for p in positions
        ):
            # RSI filter - don't sell if oversold
            if rsi is not None and rsi < self.config.rsi_oversold:
                return None

            sl, tp = self._calculate_sl_tp(bid, ask, False)

            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": self.config.lots,
                "sl": sl,
                "tp": tp,
            }

        return None

    def _calculate_sl_tp(self, bid: float, ask: float, is_buy: bool) -> tuple:
        """Calculate SL and TP based on config."""
        point = self.config.point_value

        if self.config.use_atr_sizing and len(self.prices) >= self.config.atr_period:
            atr = calculate_atr(
                self.highs[-self.config.atr_period - 5 :],
                self.lows[-self.config.atr_period - 5 :],
                self.prices[-self.config.atr_period - 5 :],
                self.config.atr_period,
            )

            if atr and atr > 0:
                sl_distance = atr * self.config.atr_sl_multiplier
                tp_distance = atr * self.config.atr_tp_multiplier
            else:
                sl_distance = self.config.stop_loss_pips * point
                tp_distance = self.config.take_profit_pips * point
        else:
            sl_distance = self.config.stop_loss_pips * point
            tp_distance = self.config.take_profit_pips * point

        if is_buy:
            sl = bid - sl_distance
            tp = ask + tp_distance
        else:
            sl = ask + sl_distance
            tp = bid - tp_distance

        return round(sl, 2), round(tp, 2)

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "trend": self.trend,
            "bars": len(self.prices),
        }
