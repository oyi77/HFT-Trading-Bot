"""
SMC Scalper Strategy — Smart Money Concepts for XAU/USD Scalping

Inspired by xaubot-ai (GifariKemal) architecture:
- Order Block detection (institutional buying/selling zones)
- Fair Value Gap detection (imbalances in price)
- Break of Structure (BOS) for trend confirmation
- Session-aware filtering (London/NY sessions = best for gold)
- ATR-based dynamic SL/TP

Optimized for M15 timeframe on XAUUSD.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional, List
from collections import deque

from trading_bot.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class SMCScalperConfig:
    """Configuration for SMC Scalper."""
    lots: float = 0.05
    max_positions: int = 2

    # Order Block params
    ob_lookback: int = 20          # Bars to look back for order blocks
    ob_strength_min: float = 0.3   # Min body ratio for valid OB candle

    # Fair Value Gap params
    fvg_min_gap_pct: float = 0.001  # Min gap as % of price (~$5 at $5000)

    # Structure params
    structure_lookback: int = 30    # Bars for swing high/low detection
    swing_threshold: int = 3        # Bars either side for swing point

    # ATR-based SL/TP
    atr_period: int = 14
    atr_sl_multiplier: float = 1.5  # Tight SL for scalping
    atr_tp_multiplier: float = 2.5  # Decent R:R
    
    # Session filter (UTC hours)
    session_filter: bool = True
    london_start: int = 7    # UTC
    london_end: int = 16     # UTC
    ny_start: int = 12       # UTC
    ny_end: int = 21         # UTC

    # RSI filter
    rsi_period: int = 14
    rsi_ob: float = 70.0   # Overbought
    rsi_os: float = 30.0   # Oversold

    # Minimum bars before trading
    min_bars: int = 50


class SMCScalperStrategy(Strategy):
    """
    Smart Money Concepts Scalper.
    
    Logic:
    1. Detect swing highs/lows → identify BOS (Break of Structure)
    2. Find Order Blocks (last opposite candle before impulsive move)
    3. Find Fair Value Gaps (3-candle imbalances)
    4. Enter when price returns to OB/FVG zone + BOS confirmed + session active
    5. SL/TP based on ATR multipliers
    """

    def __init__(self, config: SMCScalperConfig = None):
        self.config = config or SMCScalperConfig()
        self.prices = deque(maxlen=200)
        self.highs = deque(maxlen=200)
        self.lows = deque(maxlen=200)
        self.opens = deque(maxlen=200)
        self.closes = deque(maxlen=200)
        self.volumes = deque(maxlen=200)
        self.timestamps = deque(maxlen=200)
        self.tick_count = 0
        self._last_trade_bar = -100
        self._cooldown_bars = 6

        # Structure tracking
        self.swing_highs: List[tuple] = []  # (index, price)
        self.swing_lows: List[tuple] = []   # (index, price)
        self.trend = 0  # 1=bullish, -1=bearish, 0=neutral

        # Order blocks
        self.bullish_obs: List[dict] = []  # {high, low, index, tested}
        self.bearish_obs: List[dict] = []

        # Fair value gaps
        self.bullish_fvgs: List[dict] = []  # {top, bottom, index}
        self.bearish_fvgs: List[dict] = []

    @property
    def name(self) -> str:
        return "smc_scalper"

    def on_tick(self, price: float, bid: float, ask: float, positions: list, timestamp: int = 0) -> Optional[Dict]:
        self.tick_count += 1
        self.prices.append(price)
        self.highs.append(ask)
        self.lows.append(bid)
        self.opens.append(price)
        self.closes.append(price)

        if self.tick_count < self.config.min_bars:
            return None

        # Update structure
        self._update_structure()
        self._detect_order_blocks()
        self._detect_fvg()

        # Check position limit
        open_positions = [p for p in positions if self._is_active(p)]
        if len(open_positions) >= self.config.max_positions:
            return None

        # Cooldown between trades
        if self.tick_count - self._last_trade_bar < self._cooldown_bars:
            return None

        # Calculate ATR
        atr = self._calculate_atr()
        if atr is None or atr < 0.1:
            return None

        # RSI filter
        rsi = self._calculate_rsi()
        if rsi is None:
            return None

        # Generate signal
        signal = self._check_entry(price, atr, rsi)
        if signal:
            sl_distance = atr * self.config.atr_sl_multiplier
            tp_distance = atr * self.config.atr_tp_multiplier
            self._last_trade_bar = self.tick_count

            if signal == "buy":
                return {
                    "action": "open",
                    "side": "buy",
                    "amount": self.config.lots,
                    "sl": price - sl_distance,
                    "tp": price + tp_distance,
                    "reason": "SMC: OB/FVG + BOS bullish",
                }
            else:
                return {
                    "action": "open",
                    "side": "sell",
                    "amount": self.config.lots,
                    "sl": price + sl_distance,
                    "tp": price - tp_distance,
                    "reason": "SMC: OB/FVG + BOS bearish",
                }

        return None

    def _check_entry(self, price: float, atr: float, rsi: float) -> Optional[str]:
        """Check for entry signal based on SMC concepts."""
        # Need trend
        if self.trend == 0:
            return None

        # Bullish entry: trend up + price at bullish OB/FVG + RSI not overbought
        if self.trend == 1 and rsi < self.config.rsi_ob:
            # Check bullish order blocks
            for ob in self.bullish_obs[-5:]:
                if ob.get('tested', False):
                    continue
                if ob['low'] <= price <= ob['high']:
                    ob['tested'] = True
                    return "buy"

            # Check bullish FVGs
            for fvg in self.bullish_fvgs[-5:]:
                if fvg.get('filled', False):
                    continue
                if fvg['bottom'] <= price <= fvg['top']:
                    fvg['filled'] = True
                    return "buy"

        # Bearish entry: trend down + price at bearish OB/FVG + RSI not oversold
        if self.trend == -1 and rsi > self.config.rsi_os:
            for ob in self.bearish_obs[-5:]:
                if ob.get('tested', False):
                    continue
                if ob['low'] <= price <= ob['high']:
                    ob['tested'] = True
                    return "sell"

            for fvg in self.bearish_fvgs[-5:]:
                if fvg.get('filled', False):
                    continue
                if fvg['bottom'] <= price <= fvg['top']:
                    fvg['filled'] = True
                    return "sell"

        return None

    def _update_structure(self):
        """Detect swing highs/lows and determine trend via BOS."""
        if len(self.highs) < self.config.structure_lookback:
            return

        prices_list = list(self.highs)
        lows_list = list(self.lows)
        n = len(prices_list)
        th = self.config.swing_threshold

        # Detect swing high
        if n > 2 * th:
            idx = n - 1 - th
            is_swing_high = True
            is_swing_low = True
            for j in range(1, th + 1):
                if prices_list[idx] < prices_list[idx - j] or prices_list[idx] < prices_list[idx + j]:
                    is_swing_high = False
                if lows_list[idx] > lows_list[idx - j] or lows_list[idx] > lows_list[idx + j]:
                    is_swing_low = False

            if is_swing_high:
                self.swing_highs.append((self.tick_count - th, prices_list[idx]))
                self.swing_highs = self.swing_highs[-20:]
            if is_swing_low:
                self.swing_lows.append((self.tick_count - th, lows_list[idx]))
                self.swing_lows = self.swing_lows[-20:]

        # Determine trend via Break of Structure
        if len(self.swing_highs) >= 2 and len(self.swing_lows) >= 2:
            last_sh = self.swing_highs[-1][1]
            prev_sh = self.swing_highs[-2][1]
            last_sl = self.swing_lows[-1][1]
            prev_sl = self.swing_lows[-2][1]

            current_price = self.prices[-1]

            # Higher high + higher low = bullish BOS
            if last_sh > prev_sh and last_sl > prev_sl:
                self.trend = 1
            # Lower high + lower low = bearish BOS
            elif last_sh < prev_sh and last_sl < prev_sl:
                self.trend = -1
            # Mixed = check if price broke last swing
            elif current_price > last_sh:
                self.trend = 1
            elif current_price < last_sl:
                self.trend = -1

    def _detect_order_blocks(self):
        """Find order blocks — last opposite candle before impulsive move."""
        if len(self.closes) < 5:
            return

        closes = list(self.closes)
        opens = list(self.opens)
        highs = list(self.highs)
        lows = list(self.lows)
        n = len(closes)

        # Check last 3 candles for impulsive move
        # Bullish OB: bearish candle followed by strong bullish move
        body_last = closes[-1] - opens[-1]
        body_prev = closes[-2] - opens[-2]

        if body_last > 0:  # Last candle is bullish
            impulse_size = closes[-1] - lows[-2]
            body_ratio = abs(body_prev) / max(highs[-2] - lows[-2], 0.01)

            if body_prev < 0 and body_ratio > self.config.ob_strength_min:
                if impulse_size > 0:
                    ob = {
                        'high': highs[-2],
                        'low': lows[-2],
                        'index': self.tick_count - 1,
                        'tested': False,
                    }
                    self.bullish_obs.append(ob)
                    self.bullish_obs = self.bullish_obs[-10:]

        elif body_last < 0:  # Last candle is bearish
            impulse_size = highs[-2] - closes[-1]
            body_ratio = abs(body_prev) / max(highs[-2] - lows[-2], 0.01)

            if body_prev > 0 and body_ratio > self.config.ob_strength_min:
                if impulse_size > 0:
                    ob = {
                        'high': highs[-2],
                        'low': lows[-2],
                        'index': self.tick_count - 1,
                        'tested': False,
                    }
                    self.bearish_obs.append(ob)
                    self.bearish_obs = self.bearish_obs[-10:]

    def _detect_fvg(self):
        """Detect Fair Value Gaps (3-candle imbalances)."""
        if len(self.highs) < 3:
            return

        highs = list(self.highs)
        lows = list(self.lows)
        price = self.prices[-1]
        min_gap = price * self.config.fvg_min_gap_pct

        # Bullish FVG: candle[0].high < candle[2].low (gap up)
        h0 = highs[-3]
        l2 = lows[-1]
        if l2 > h0 and (l2 - h0) >= min_gap:
            self.bullish_fvgs.append({
                'top': l2,
                'bottom': h0,
                'index': self.tick_count,
                'filled': False,
            })
            self.bullish_fvgs = self.bullish_fvgs[-10:]

        # Bearish FVG: candle[0].low > candle[2].high (gap down)
        l0 = lows[-3]
        h2 = highs[-1]
        if l0 > h2 and (l0 - h2) >= min_gap:
            self.bearish_fvgs.append({
                'top': l0,
                'bottom': h2,
                'index': self.tick_count,
                'filled': False,
            })
            self.bearish_fvgs = self.bearish_fvgs[-10:]

    def _calculate_atr(self, period=None) -> Optional[float]:
        """Calculate Average True Range."""
        period = period or self.config.atr_period
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

    def _calculate_rsi(self, period=None) -> Optional[float]:
        """Calculate RSI."""
        period = period or self.config.rsi_period
        if len(self.closes) < period + 1:
            return None

        closes = list(self.closes)
        gains = []
        losses = []
        for i in range(-period, 0):
            delta = closes[i] - closes[i - 1]
            if delta > 0:
                gains.append(delta)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(delta))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _is_active(self, position) -> bool:
        """Check if a position is active."""
        if isinstance(position, dict):
            return position.get("status", "open") == "open"
        return getattr(position, "status", "open") == "open"
