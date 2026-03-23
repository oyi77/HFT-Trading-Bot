"""
Mean Reversion Scalper — Bollinger Bands + RSI + VWAP for XAU/USD Scalping

Key principle: Gold on short timeframes (M5/M15) mean-reverts strongly.
When price hits extreme BB bands + RSI diverges + price far from VWAP → snap back.

Features:
- Dual Bollinger Bands (2σ entry zone, 3σ extreme zone)
- RSI divergence for confirmation
- ATR-based dynamic SL/TP (tight for scalping)
- Z-score of price from VWAP for additional filter
- Momentum exhaustion detection (body shrinkage + wick growth)

Optimized for M5/M15 XAUUSD scalping.
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional
from collections import deque

from trading_bot.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionConfig:
    """Configuration for Mean Reversion Scalper."""
    lots: float = 0.05
    max_positions: int = 2

    # Bollinger Bands
    bb_period: int = 20
    bb_std_entry: float = 2.0      # Entry zone (standard BB)
    bb_std_extreme: float = 2.5    # Extreme zone (stronger signal)

    # RSI
    rsi_period: int = 14
    rsi_ob: float = 75.0           # Overbought → sell signal
    rsi_os: float = 25.0           # Oversold → buy signal

    # VWAP-like moving average (volume-weighted proxy)
    vwap_period: int = 50
    vwap_zscore_threshold: float = 1.5  # How far from VWAP to trigger

    # ATR SL/TP
    atr_period: int = 14
    atr_sl_multiplier: float = 1.2  # Very tight SL for scalping
    atr_tp_multiplier: float = 1.8  # Quick TP

    # Momentum exhaustion
    exhaustion_bars: int = 3       # Check last N bars for exhaustion
    body_shrink_ratio: float = 0.5 # Body must be < 50% of wick

    # Minimum bars
    min_bars: int = 60


class MeanReversionScalper(Strategy):
    """
    Mean Reversion Scalper for XAU/USD.

    Entry logic:
    1. Price at/beyond BB outer band (2σ or 3σ)
    2. RSI at extreme (>75 or <25)
    3. Price far from VWAP (z-score > threshold)
    4. Momentum exhaustion detected (candle body shrinking)
    → Enter counter-trend

    Exit: ATR-based SL/TP
    """

    def __init__(self, config: MeanReversionConfig = None):
        self.config = config or MeanReversionConfig()
        self.closes = deque(maxlen=200)
        self.highs = deque(maxlen=200)
        self.lows = deque(maxlen=200)
        self.opens = deque(maxlen=200)
        self.tick_count = 0
        self._last_trade_bar = -100
        self._cooldown_bars = 8  # min bars between entries

    @property
    def name(self) -> str:
        return "mean_reversion"

    def on_tick(self, price: float, bid: float, ask: float, positions: list, timestamp: int = 0) -> Optional[Dict]:
        self.tick_count += 1
        self.closes.append(price)
        self.highs.append(max(price, ask))
        self.lows.append(min(price, bid))
        self.opens.append(price)

        if self.tick_count < self.config.min_bars:
            return None

        # Check position limit
        open_positions = [p for p in positions if self._is_active(p)]
        if len(open_positions) >= self.config.max_positions:
            return None

        # Cooldown: avoid overtrading
        if self.tick_count - self._last_trade_bar < self._cooldown_bars:
            return None

        # Calculate indicators
        bb = self._bollinger_bands()
        rsi = self._rsi()
        atr = self._atr()
        vwap_z = self._vwap_zscore()

        if bb is None or rsi is None or atr is None or atr < 0.1:
            return None

        sma, upper_entry, lower_entry, upper_extreme, lower_extreme = bb

        # Score system: accumulate evidence for entry
        buy_score = 0
        sell_score = 0

        # BB signals
        if price <= lower_entry:
            buy_score += 1
        if price <= lower_extreme:
            buy_score += 1  # Extra point for extreme

        if price >= upper_entry:
            sell_score += 1
        if price >= upper_extreme:
            sell_score += 1

        # RSI signals
        if rsi <= self.config.rsi_os:
            buy_score += 1
        elif rsi <= 35:
            buy_score += 0.5

        if rsi >= self.config.rsi_ob:
            sell_score += 1
        elif rsi >= 65:
            sell_score += 0.5

        # VWAP z-score
        if vwap_z is not None:
            if vwap_z < -self.config.vwap_zscore_threshold:
                buy_score += 1
            if vwap_z > self.config.vwap_zscore_threshold:
                sell_score += 1

        # Momentum exhaustion
        if self._check_exhaustion("bearish"):
            buy_score += 0.5
        if self._check_exhaustion("bullish"):
            sell_score += 0.5

        # Need at least 3.5 points to enter (strong confluence required)
        sl_dist = atr * self.config.atr_sl_multiplier
        tp_dist = atr * self.config.atr_tp_multiplier

        if buy_score >= 3.5:
            self._last_trade_bar = self.tick_count
            return {
                "action": "open",
                "side": "buy",
                "amount": self.config.lots,
                "sl": price - sl_dist,
                "tp": price + tp_dist,
                "reason": f"MeanRev BUY: score={buy_score:.1f} RSI={rsi:.0f} BB_low",
            }

        if sell_score >= 3.5:
            self._last_trade_bar = self.tick_count
            return {
                "action": "open",
                "side": "sell",
                "amount": self.config.lots,
                "sl": price + sl_dist,
                "tp": price - tp_dist,
                "reason": f"MeanRev SELL: score={sell_score:.1f} RSI={rsi:.0f} BB_high",
            }

        return None

    def _bollinger_bands(self):
        """Calculate dual Bollinger Bands."""
        period = self.config.bb_period
        if len(self.closes) < period:
            return None

        data = list(self.closes)[-period:]
        sma = sum(data) / period
        variance = sum((x - sma) ** 2 for x in data) / period
        std = math.sqrt(variance)

        upper_entry = sma + self.config.bb_std_entry * std
        lower_entry = sma - self.config.bb_std_entry * std
        upper_extreme = sma + self.config.bb_std_extreme * std
        lower_extreme = sma - self.config.bb_std_extreme * std

        return sma, upper_entry, lower_entry, upper_extreme, lower_extreme

    def _rsi(self) -> Optional[float]:
        """Calculate RSI."""
        period = self.config.rsi_period
        if len(self.closes) < period + 1:
            return None

        closes = list(self.closes)
        gains, losses = [], []
        for i in range(-period, 0):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    def _atr(self) -> Optional[float]:
        """Calculate ATR."""
        period = self.config.atr_period
        if len(self.highs) < period + 1:
            return None

        highs = list(self.highs)
        lows = list(self.lows)
        closes = list(self.closes)
        trs = []
        for i in range(-period, 0):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return sum(trs) / len(trs)

    def _vwap_zscore(self) -> Optional[float]:
        """Calculate z-score of price from moving average (VWAP proxy)."""
        period = self.config.vwap_period
        if len(self.closes) < period:
            return None

        data = list(self.closes)[-period:]
        mean = sum(data) / period
        variance = sum((x - mean) ** 2 for x in data) / period
        std = math.sqrt(variance)
        if std < 0.01:
            return 0.0
        return (self.closes[-1] - mean) / std

    def _check_exhaustion(self, direction: str) -> bool:
        """Check for momentum exhaustion candles."""
        n = self.config.exhaustion_bars
        if len(self.closes) < n + 1:
            return False

        closes = list(self.closes)
        opens = list(self.opens)
        highs = list(self.highs)
        lows = list(self.lows)

        for i in range(-n, 0):
            body = abs(closes[i] - opens[i])
            wick = highs[i] - lows[i]
            if wick < 0.01:
                return False
            ratio = body / wick
            if ratio > self.config.body_shrink_ratio:
                return False  # Body still strong, no exhaustion

            # Check direction
            if direction == "bearish" and closes[i] > opens[i]:
                return False  # Not bearish
            if direction == "bullish" and closes[i] < opens[i]:
                return False  # Not bullish

        return True

    def _is_active(self, position) -> bool:
        if isinstance(position, dict):
            return position.get("status", "open") == "open"
        return getattr(position, "status", "open") == "open"
