"""
Bollinger Band + MACD + RSI Strategy
Combines three powerful indicators for high-probability mean-reversion & breakout trades.

Entry rules:
- BUY:  Price at/below lower BB + RSI < 35 + MACD histogram turning positive
- SELL: Price at/above upper BB + RSI > 65 + MACD histogram turning negative

SL/TP: ATR-based adaptive risk management (default 2x ATR stop, 3x ATR target).
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from collections import deque

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide
from trading_bot.utils.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_bollinger_bands,
)


@dataclass
class BBMacdRsiConfig:
    """Configuration for BB + MACD + RSI Strategy"""

    # Trade parameters
    lots: float = 0.01
    max_positions: int = 2

    # Bollinger Bands
    bb_period: int = 20
    bb_std_dev: float = 2.0

    # RSI
    rsi_period: int = 14
    rsi_overbought: float = 60.0
    rsi_oversold: float = 40.0

    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # ATR-based SL/TP
    atr_period: int = 14
    atr_sl_multiplier: float = 2.0
    atr_tp_multiplier: float = 3.0

    # Squeeze detection (BB width relative to price)
    squeeze_threshold: float = 0.005  # BB width < 0.5% of price = squeeze
    use_squeeze_filter: bool = True

    # Cooldown
    min_bars_between_trades: int = 3

    # Point value
    point_value: float = 0.01


class BBMacdRsiStrategy(Strategy):
    """
    Bollinger Band + MACD + RSI Strategy

    Combines mean-reversion (BB) with momentum confirmation (MACD + RSI)
    for high-probability entries. ATR-based risk management adapts to
    current market volatility.

    Modes:
    1. Mean Reversion: Buy at lower BB with RSI oversold + MACD upturn
    2. Breakout: Enter after BB squeeze expansion with momentum confirmation
    """

    def __init__(self, config: BBMacdRsiConfig = None):
        if config is None:
            config = BBMacdRsiConfig()
        super().__init__(config)

        self.closes: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []

        # MACD history for histogram direction
        self.macd_hist: List[float] = []

        # Trade tracking
        self.bars_since_trade = 999
        self.tick_count = 0

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        self.tick_count += 1
        self.bars_since_trade += 1

        mid = (bid + ask) / 2
        self.closes.append(mid)
        self.highs.append(ask)
        self.lows.append(bid)

        # Keep bounded history
        max_len = max(self.config.bb_period, self.config.macd_slow + self.config.macd_signal, self.config.atr_period) + 50
        if len(self.closes) > max_len:
            self.closes = self.closes[-max_len:]
            self.highs = self.highs[-max_len:]
            self.lows = self.lows[-max_len:]

        # Need enough data for all indicators
        min_bars = self.config.macd_slow + self.config.macd_signal + 5
        if len(self.closes) < min_bars:
            return None

        # Manage existing positions first
        action = self._manage_positions(positions, bid, ask)
        if action:
            return action

        # Check position limit
        if len(positions) >= self.config.max_positions:
            return None

        # Cooldown
        if self.bars_since_trade < self.config.min_bars_between_trades:
            return None

        # Compute indicators
        bb = calculate_bollinger_bands(self.closes, self.config.bb_period, self.config.bb_std_dev)
        rsi = calculate_rsi(self.closes, self.config.rsi_period)
        atr = calculate_atr(self.highs, self.lows, self.closes, self.config.atr_period)

        if bb is None or rsi is None:
            return None

        upper_bb, middle_bb, lower_bb = bb

        # MACD calculation
        macd_data = self._calculate_macd()
        if macd_data is None:
            return None

        macd_line, signal_line, histogram = macd_data
        self.macd_hist.append(histogram)
        if len(self.macd_hist) > 50:
            self.macd_hist = self.macd_hist[-50:]

        # Check histogram direction (turning)
        hist_turning_up = len(self.macd_hist) >= 2 and self.macd_hist[-1] > self.macd_hist[-2]
        hist_turning_down = len(self.macd_hist) >= 2 and self.macd_hist[-1] < self.macd_hist[-2]

        # Squeeze detection
        bb_width = (upper_bb - lower_bb) / middle_bb if middle_bb > 0 else 0
        in_squeeze = bb_width < self.config.squeeze_threshold

        # Default SL/TP distances
        if atr and atr > 0:
            sl_dist = atr * self.config.atr_sl_multiplier
            tp_dist = atr * self.config.atr_tp_multiplier
        else:
            sl_dist = 10 * self.config.point_value
            tp_dist = 15 * self.config.point_value

        # ── BUY SIGNAL ──
        # Price at or below lower BB + RSI oversold + MACD histogram turning up
        buy_bb = mid <= lower_bb * 1.001  # within 0.1% of lower BB
        buy_rsi = rsi < self.config.rsi_oversold
        buy_macd = hist_turning_up

        if buy_bb and buy_rsi and buy_macd:
            if not any(p.side == PositionSide.LONG for p in positions):
                sl = bid - sl_dist
                tp = ask + tp_dist
                self.bars_since_trade = 0
                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        # ── SELL SIGNAL ──
        # Price at or above upper BB + RSI overbought + MACD histogram turning down
        sell_bb = mid >= upper_bb * 0.999  # within 0.1% of upper BB
        sell_rsi = rsi > self.config.rsi_overbought
        sell_macd = hist_turning_down

        if sell_bb and sell_rsi and sell_macd:
            if not any(p.side == PositionSide.SHORT for p in positions):
                sl = ask + sl_dist
                tp = bid - tp_dist
                self.bars_since_trade = 0
                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        # ── SQUEEZE BREAKOUT ──
        # After squeeze, if price breaks out with momentum
        if self.config.use_squeeze_filter and not in_squeeze and len(self.macd_hist) >= 3:
            # Check if was in squeeze recently (within last 10 bars)
            recent_widths = []
            for i in range(max(0, len(self.closes) - 10), len(self.closes) - 1):
                bb_i = calculate_bollinger_bands(self.closes[:i+1], self.config.bb_period, self.config.bb_std_dev)
                if bb_i:
                    w = (bb_i[0] - bb_i[2]) / bb_i[1] if bb_i[1] > 0 else 0
                    recent_widths.append(w)

            was_squeezed = any(w < self.config.squeeze_threshold for w in recent_widths[-5:]) if recent_widths else False

            if was_squeezed:
                # Breakout up
                if mid > upper_bb and macd_line > signal_line and rsi > 50 and rsi < 75:
                    if not any(p.side == PositionSide.LONG for p in positions):
                        sl = bid - sl_dist
                        tp = ask + tp_dist * 1.5  # Wider TP for breakouts
                        self.bars_since_trade = 0
                        return {
                            "action": "open",
                            "side": OrderSide.BUY,
                            "amount": self.config.lots,
                            "sl": round(sl, 2),
                            "tp": round(tp, 2),
                        }

                # Breakout down
                if mid < lower_bb and macd_line < signal_line and rsi < 50 and rsi > 25:
                    if not any(p.side == PositionSide.SHORT for p in positions):
                        sl = ask + sl_dist
                        tp = bid - tp_dist * 1.5
                        self.bars_since_trade = 0
                        return {
                            "action": "open",
                            "side": OrderSide.SELL,
                            "amount": self.config.lots,
                            "sl": round(sl, 2),
                            "tp": round(tp, 2),
                        }

        return None

    def _manage_positions(
        self, positions: List[Position], bid: float, ask: float
    ) -> Optional[Dict]:
        """Manage positions with TP/SL checking."""
        for pos in positions:
            # Check TP
            if pos.tp:
                if pos.side == PositionSide.LONG and bid >= pos.tp:
                    return {"action": "close", "position_id": pos.id}
                if pos.side == PositionSide.SHORT and ask <= pos.tp:
                    return {"action": "close", "position_id": pos.id}

            # Check SL
            if pos.sl:
                if pos.side == PositionSide.LONG and bid <= pos.sl:
                    return {"action": "close", "position_id": pos.id}
                if pos.side == PositionSide.SHORT and ask >= pos.sl:
                    return {"action": "close", "position_id": pos.id}

        return None

    def _calculate_macd(self) -> Optional[tuple]:
        """Calculate MACD with proper signal line using EMA of MACD history."""
        fast_ema = calculate_ema(self.closes, self.config.macd_fast)
        slow_ema = calculate_ema(self.closes, self.config.macd_slow)

        if fast_ema is None or slow_ema is None:
            return None

        macd_line = fast_ema - slow_ema

        # Build MACD line history for signal line calculation
        # We need enough MACD values for the signal EMA
        macd_values = []
        for i in range(self.config.macd_slow, len(self.closes) + 1):
            subset = self.closes[:i]
            f = calculate_ema(subset, self.config.macd_fast)
            s = calculate_ema(subset, self.config.macd_slow)
            if f is not None and s is not None:
                macd_values.append(f - s)

        if len(macd_values) < self.config.macd_signal:
            return None

        signal_line = calculate_ema(macd_values, self.config.macd_signal)
        if signal_line is None:
            return None

        histogram = macd_line - signal_line
        return (macd_line, signal_line, histogram)

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "tick_count": self.tick_count,
            "bars": len(self.closes),
            "bars_since_trade": self.bars_since_trade,
        }
