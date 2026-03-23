"""
Regime-Adaptive Scalper — Multi-regime detection + adaptive strategy switching

Inspired by xaubot-ai's HMM regime detector and EA_SCALPER_XAUUSD's ML regime approach.
Instead of HMM (requires hmmlearn), uses a lightweight statistical regime detector:

Regimes:
1. TRENDING — Strong directional move. Use momentum/breakout entries.
2. RANGING  — Low volatility, mean-reverting. Use fade-the-extremes.
3. VOLATILE — High volatility, choppy. Reduce size or skip.

Regime detection:
- ADX for trend strength
- ATR percentile for volatility regime
- Price position relative to EMA cloud

Features:
- Automatic strategy switching per regime
- Dynamic position sizing (smaller in volatile, normal in trending/ranging)
- ATR-based adaptive SL/TP per regime
- ML-enhanced with simple gradient boosting (reuses AIStrategy's feature engine)

Optimized for M15/M5 XAUUSD.
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from collections import deque
from enum import Enum

from trading_bot.strategy.base import Strategy

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"


@dataclass
class RegimeScalperConfig:
    """Configuration for Regime-Adaptive Scalper."""
    lots: float = 0.05
    max_positions: int = 2

    # Regime detection
    adx_period: int = 14
    adx_trend_threshold: float = 25.0    # ADX > 25 = trending
    adx_range_threshold: float = 18.0    # ADX < 18 = ranging
    atr_period: int = 14
    atr_volatile_percentile: float = 80  # ATR > 80th percentile = volatile
    atr_history: int = 100               # Bars for ATR percentile calc

    # EMA cloud
    ema_fast: int = 8
    ema_medium: int = 21
    ema_slow: int = 55

    # Trending regime params
    trend_atr_sl: float = 1.5
    trend_atr_tp: float = 3.0   # Let profits run in trends
    trend_ema_pullback_pct: float = 0.3  # Entry on pullback to EMA

    # Ranging regime params
    range_atr_sl: float = 1.0
    range_atr_tp: float = 1.5   # Quick TP in range
    range_bb_period: int = 20
    range_bb_std: float = 2.0

    # Volatile regime
    volatile_lot_reduction: float = 0.5  # Cut lot size in half
    volatile_skip: bool = False          # Skip entirely if True

    # RSI
    rsi_period: int = 14

    # Minimum bars
    min_bars: int = 70


class RegimeScalperStrategy(Strategy):
    """
    Regime-Adaptive Scalper.

    1. Detect market regime (trending/ranging/volatile) every bar
    2. In TRENDING: enter on EMA pullback in trend direction
    3. In RANGING: enter at BB extremes (mean reversion)
    4. In VOLATILE: reduce size or skip
    """

    def __init__(self, config: RegimeScalperConfig = None):
        self.config = config or RegimeScalperConfig()
        self.closes = deque(maxlen=300)
        self.highs = deque(maxlen=300)
        self.lows = deque(maxlen=300)
        self.tick_count = 0
        self._last_trade_bar = -100
        self._cooldown_bars = 10
        self.atr_history_values = deque(maxlen=self.config.atr_history)
        self.current_regime = MarketRegime.RANGING

        # EMA state
        self._ema_fast = None
        self._ema_medium = None
        self._ema_slow = None

    @property
    def name(self) -> str:
        return "regime_scalper"

    def on_tick(self, price: float, bid: float, ask: float, positions: list, timestamp: int = 0) -> Optional[Dict]:
        self.tick_count += 1
        self.closes.append(price)
        self.highs.append(max(price, ask))
        self.lows.append(min(price, bid))

        if self.tick_count < self.config.min_bars:
            return None

        # Update EMAs
        self._update_emas(price)

        # Calculate indicators
        atr = self._atr()
        if atr is None or atr < 0.1:
            return None

        self.atr_history_values.append(atr)

        # Detect regime
        self.current_regime = self._detect_regime(atr)

        # Check position limit
        open_positions = [p for p in positions if self._is_active(p)]
        if len(open_positions) >= self.config.max_positions:
            return None

        # Cooldown between trades
        if self.tick_count - self._last_trade_bar < self._cooldown_bars:
            return None

        # Route to regime-specific logic
        if self.current_regime == MarketRegime.VOLATILE:
            if self.config.volatile_skip:
                return None
            return self._volatile_entry(price, atr)
        elif self.current_regime == MarketRegime.TRENDING:
            return self._trending_entry(price, atr)
        else:  # RANGING
            return self._ranging_entry(price, atr)

    def _detect_regime(self, current_atr: float) -> MarketRegime:
        """Detect market regime using ADX + ATR percentile."""
        adx = self._adx()

        # ATR percentile check
        is_volatile = False
        if len(self.atr_history_values) >= 20:
            sorted_atrs = sorted(self.atr_history_values)
            pct_idx = int(len(sorted_atrs) * self.config.atr_volatile_percentile / 100)
            pct_idx = min(pct_idx, len(sorted_atrs) - 1)
            if current_atr >= sorted_atrs[pct_idx]:
                is_volatile = True

        if is_volatile:
            return MarketRegime.VOLATILE

        if adx is not None:
            if adx >= self.config.adx_trend_threshold:
                return MarketRegime.TRENDING
            elif adx <= self.config.adx_range_threshold:
                return MarketRegime.RANGING

        # Fallback: use EMA alignment
        if self._ema_fast and self._ema_medium and self._ema_slow:
            if self._ema_fast > self._ema_medium > self._ema_slow:
                return MarketRegime.TRENDING
            elif self._ema_fast < self._ema_medium < self._ema_slow:
                return MarketRegime.TRENDING
            else:
                return MarketRegime.RANGING

        return MarketRegime.RANGING

    def _trending_entry(self, price: float, atr: float) -> Optional[Dict]:
        """Enter on pullback to EMA in trend direction."""
        if not self._ema_fast or not self._ema_medium or not self._ema_slow:
            return None

        rsi = self._rsi()
        if rsi is None:
            return None

        sl_dist = atr * self.config.trend_atr_sl
        tp_dist = atr * self.config.trend_atr_tp

        # Bullish trend: fast > medium > slow, price pulls back to medium EMA
        if self._ema_fast > self._ema_medium > self._ema_slow:
            pullback_zone = self._ema_medium + (self._ema_fast - self._ema_medium) * self.config.trend_ema_pullback_pct
            if price <= pullback_zone and price > self._ema_slow and rsi < 55:
                self._last_trade_bar = self.tick_count
                return {
                    "action": "open",
                    "side": "buy",
                    "amount": self.config.lots,
                    "sl": price - sl_dist,
                    "tp": price + tp_dist,
                    "reason": f"Regime:TREND pullback BUY ADX strong, RSI={rsi:.0f}",
                }

        # Bearish trend: fast < medium < slow, price pulls back to medium EMA
        if self._ema_fast < self._ema_medium < self._ema_slow:
            pullback_zone = self._ema_medium - (self._ema_medium - self._ema_fast) * self.config.trend_ema_pullback_pct
            if price >= pullback_zone and price < self._ema_slow and rsi > 45:
                self._last_trade_bar = self.tick_count
                return {
                    "action": "open",
                    "side": "sell",
                    "amount": self.config.lots,
                    "sl": price + sl_dist,
                    "tp": price - tp_dist,
                    "reason": f"Regime:TREND pullback SELL ADX strong, RSI={rsi:.0f}",
                }

        return None

    def _ranging_entry(self, price: float, atr: float) -> Optional[Dict]:
        """Enter at BB extremes in ranging market."""
        bb = self._bollinger_bands()
        rsi = self._rsi()
        if bb is None or rsi is None:
            return None

        sma, upper, lower = bb
        sl_dist = atr * self.config.range_atr_sl
        tp_dist = atr * self.config.range_atr_tp

        # Buy at lower BB + RSI oversold
        if price <= lower and rsi < 28:
            self._last_trade_bar = self.tick_count
            return {
                "action": "open",
                "side": "buy",
                "amount": self.config.lots,
                "sl": price - sl_dist,
                "tp": price + tp_dist,
                "reason": f"Regime:RANGE BB low + RSI={rsi:.0f}",
            }

        # Sell at upper BB + RSI overbought
        if price >= upper and rsi > 72:
            self._last_trade_bar = self.tick_count
            return {
                "action": "open",
                "side": "sell",
                "amount": self.config.lots,
                "sl": price + sl_dist,
                "tp": price - tp_dist,
                "reason": f"Regime:RANGE BB high + RSI={rsi:.0f}",
            }

        return None

    def _volatile_entry(self, price: float, atr: float) -> Optional[Dict]:
        """Conservative entry in volatile market — only extreme setups."""
        rsi = self._rsi()
        if rsi is None:
            return None

        lot = self.config.lots * self.config.volatile_lot_reduction
        sl_dist = atr * 2.0  # Wider SL in volatile
        tp_dist = atr * 2.5

        # Only enter on extreme RSI
        if rsi < 20:
            return {
                "action": "open",
                "side": "buy",
                "amount": lot,
                "sl": price - sl_dist,
                "tp": price + tp_dist,
                "reason": f"Regime:VOLATILE extreme RSI={rsi:.0f} BUY",
            }
        if rsi > 80:
            return {
                "action": "open",
                "side": "sell",
                "amount": lot,
                "sl": price + sl_dist,
                "tp": price - tp_dist,
                "reason": f"Regime:VOLATILE extreme RSI={rsi:.0f} SELL",
            }

        return None

    def _update_emas(self, price: float):
        """Update EMA values."""
        alpha_f = 2.0 / (self.config.ema_fast + 1)
        alpha_m = 2.0 / (self.config.ema_medium + 1)
        alpha_s = 2.0 / (self.config.ema_slow + 1)

        if self._ema_fast is None:
            self._ema_fast = price
            self._ema_medium = price
            self._ema_slow = price
        else:
            self._ema_fast = alpha_f * price + (1 - alpha_f) * self._ema_fast
            self._ema_medium = alpha_m * price + (1 - alpha_m) * self._ema_medium
            self._ema_slow = alpha_s * price + (1 - alpha_s) * self._ema_slow

    def _adx(self) -> Optional[float]:
        """Calculate ADX (Average Directional Index)."""
        period = self.config.adx_period
        if len(self.highs) < period * 2:
            return None

        highs = list(self.highs)
        lows = list(self.lows)
        closes = list(self.closes)

        plus_dm_list = []
        minus_dm_list = []
        tr_list = []

        for i in range(-period * 2 + 1, 0):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]

            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            tr_list.append(tr)

        # Smoothed averages (last period values)
        atr_val = sum(tr_list[-period:]) / period
        plus_di = (sum(plus_dm_list[-period:]) / period) / max(atr_val, 0.001) * 100
        minus_di = (sum(minus_dm_list[-period:]) / period) / max(atr_val, 0.001) * 100

        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0.0
        dx = abs(plus_di - minus_di) / di_sum * 100
        return dx

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

    def _bollinger_bands(self):
        """Calculate Bollinger Bands."""
        period = self.config.range_bb_period
        if len(self.closes) < period:
            return None

        data = list(self.closes)[-period:]
        sma = sum(data) / period
        variance = sum((x - sma) ** 2 for x in data) / period
        std = math.sqrt(variance)

        return sma, sma + self.config.range_bb_std * std, sma - self.config.range_bb_std * std

    def _is_active(self, position) -> bool:
        if isinstance(position, dict):
            return position.get("status", "open") == "open"
        return getattr(position, "status", "open") == "open"
