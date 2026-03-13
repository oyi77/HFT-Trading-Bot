"""
7 Candle Breakout Strategy
Based on the \"7 Candle System\" - a popular trading system

Logic:
- Wait for 7 consecutive candles in the same direction
- Enter on breakout of the 7th candle's high/low
- Use ATR for stop loss and take profit
"""

from typing import Dict, Optional, List
from dataclasses import dataclass

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class SevenCandleConfig:
    """Configuration for 7 Candle Breakout Strategy"""

    lots: float = 0.01

    # Number of consecutive candles
    candle_count: int = 5  # Reduced from 7 for more signals

    # Minimum percentage of candles that must match direction
    min_match_pct: float = 0.8  # 80% = 4/5 candles must agree

    # ATR-based stops
    use_atr_stops: bool = True
    atr_period: int = 14
    atr_multiplier_sl: float = 1.5
    atr_multiplier_tp: float = 2.5

    # Alternative: fixed pips
    fixed_sl_pips: int = 50
    fixed_tp_pips: int = 120

    # Confirmation
    require_close: bool = True  # Wait for candle close

    # Point value
    point_value: float = 0.01

    # Max positions
    max_positions: int = 1


class SevenCandleStrategy(Strategy):
    """
    7 Candle Breakout Strategy

    Entry rules:
    1. Wait for 7 consecutive candles in same direction
    2. Price breaks above/below the high/low of the 7th candle
    3. Enter in direction of the trend

    Exit rules:
    - Stop loss: Below/above entry by ATR * multiplier
    - Take profit: Above/below entry by ATR * multiplier * 1.5
    """

    def __init__(self, config: SevenCandleConfig = None):
        if config is None:
            config = SevenCandleConfig()
        super().__init__(config)

        self.prices: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []
        self.closes: List[float] = []

        # Track consecutive candles
        self.consecutive_count = 0
        self.last_direction = None

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
        self.highs.append(ask)  # Use ask as high approximation
        self.lows.append(bid)  # Use bid as low approximation
        self.closes.append(price)

        # Keep enough history
        if len(self.prices) > self.config.candle_count + 10:
            self.prices = self.prices[-self.config.candle_count - 10 :]
            self.highs = self.highs[-self.config.candle_count - 10 :]
            self.lows = self.lows[-self.config.candle_count - 10 :]
            self.closes = self.closes[-self.config.candle_count - 10 :]

        # Need enough data
        if len(self.prices) < self.config.candle_count + 2:
            return None

        # Manage existing positions
        if positions:
            return self._manage_positions(positions, bid, ask, point)

        # Check position limit
        if len(positions) >= self.config.max_positions:
            return None

        # Analyze for entry
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
            if pos.tp:
                if pos.side == PositionSide.LONG and bid >= pos.tp:
                    return {"action": "close", "position_id": pos.id}
                elif pos.side == PositionSide.SHORT and ask <= pos.tp:
                    return {"action": "close", "position_id": pos.id}

            # Check SL
            if pos.sl:
                if pos.side == PositionSide.LONG and bid <= pos.sl:
                    return {"action": "close", "position_id": pos.id}
                elif pos.side == PositionSide.SHORT and ask >= pos.sl:
                    return {"action": "close", "position_id": pos.id}

        return None

    def _analyze_entry(self, bid: float, ask: float, point: float) -> Optional[Dict]:
        """Analyze for 7 candle breakout entry"""

        # Get last N candles
        n = self.config.candle_count
        recent_closes = self.closes[-n - 1 : -1]  # Previous n closes
        recent_highs = self.highs[-n - 1 : -1]
        recent_lows = self.lows[-n - 1 : -1]

        if len(recent_closes) < n:
            return None

        # Check if most candles are bullish (close increasing)
        bullish_count = sum(1 for i in range(n - 1) if recent_closes[i] < recent_closes[i + 1])
        bearish_count = sum(1 for i in range(n - 1) if recent_closes[i] > recent_closes[i + 1])
        
        min_required = int((n - 1) * self.config.min_match_pct)
        
        mostly_bullish = bullish_count >= min_required
        mostly_bearish = bearish_count >= min_required

        # Get breakout levels
        seventh_high = recent_highs[-1]
        seventh_low = recent_lows[-1]

        current_price = self.closes[-1]

        # Bullish breakout: price breaks above 7th candle's high
        if mostly_bullish and current_price > seventh_high:
            sl, tp = self._calculate_sl_tp(bid, ask, True, point)

            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        # Bearish breakout: price breaks below 7th candle's low
        if mostly_bearish and current_price < seventh_low:
            sl, tp = self._calculate_sl_tp(bid, ask, False, point)

            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        return None

    def _calculate_sl_tp(
        self, bid: float, ask: float, is_long: bool, point: float
    ) -> tuple:
        """Calculate stop loss and take profit"""

        if self.config.use_atr_stops and len(self.highs) >= self.config.atr_period:
            # Calculate ATR
            atr = self._calculate_atr()
            if atr:
                sl_distance = atr * self.config.atr_multiplier_sl
                tp_distance = atr * self.config.atr_multiplier_tp
            else:
                sl_distance = self.config.fixed_sl_pips * point
                tp_distance = self.config.fixed_tp_pips * point
        else:
            sl_distance = self.config.fixed_sl_pips * point
            tp_distance = self.config.fixed_tp_pips * point

        if is_long:
            sl = bid - sl_distance
            tp = ask + tp_distance
        else:
            sl = ask + sl_distance
            tp = bid - tp_distance

        return sl, tp

    def _calculate_atr(self) -> Optional[float]:
        """Calculate Average True Range"""
        if len(self.highs) < self.config.atr_period + 1:
            return None

        tr_values = []
        for i in range(1, len(self.highs)):
            high = self.highs[i]
            low = self.lows[i]
            prev_close = self.closes[i - 1]

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        if len(tr_values) < self.config.atr_period:
            return None

        atr = sum(tr_values[-self.config.atr_period :]) / self.config.atr_period
        return atr

    def get_stats(self) -> Dict:
        return {
            "candles_tracked": len(self.prices),
            "consecutive": self.consecutive_count,
        }
