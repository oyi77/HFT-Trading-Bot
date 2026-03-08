"""
NostalgiaForInfinity (NFI) Strategy
Multi-mode trend following strategy - one of Freqtrade's most profitable.

Modes:
- normal: Standard trend following
- pump: Aggressive entries on strong momentum
- quick: Quick scalping mode
- scalp: Ultra-short-term scalping

Key features:
- Multiple EMA confirmation
- RSI for overbought/oversold
- Volume confirmation
- Dynamic TP/SL based on ATR
"""

from typing import Dict, Optional, List, Deque
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide
from trading_bot.utils.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_sma,
)


class NFIMode(Enum):
    NORMAL = "normal"
    PUMP = "pump"
    QUICK = "quick"
    SCALP = "scalp"


@dataclass
class NFIConfig:
    """Configuration for NFI Strategy"""

    # Trade parameters
    lots: float = 0.01
    max_positions: int = 3

    # Mode selection
    mode: str = "normal"  # normal, pump, quick, scalp

    # EMA periods
    ema_fast: int = 8
    ema_medium: int = 13
    ema_slow: int = 21
    ema_trend: int = 50

    # RSI parameters
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # ATR-based TP/SL
    atr_period: int = 14
    atr_tp_multiplier: float = 2.0
    atr_sl_multiplier: float = 1.5

    # Volume filter
    volume_period: int = 20
    volume_multiplier: float = 1.2

    # Risk management
    max_daily_loss: float = 100.0
    cooldown_minutes: int = 5

    # Mode-specific thresholds
    pump_momentum_threshold: float = 0.003  # 0.3% for pump mode
    quick_profit_pips: int = 5
    scalp_profit_pips: int = 3

    # Point value
    point_value: float = 0.01


class NFIStrategy(Strategy):
    """
    NostalgiaForInfinity Strategy - Multi-mode trend following.

    Based on Freqtrade's most profitable community strategy.
    Combines multiple EMA signals with RSI and volume confirmation.
    """

    def __init__(self, config: NFIConfig = None):
        if config is None:
            config = NFIConfig()
        super().__init__(config)

        # Price history
        self.price_history: Deque[Dict] = deque(maxlen=200)
        self.high_history: Deque[float] = deque(maxlen=100)
        self.low_history: Deque[float] = deque(maxlen=100)
        self.close_history: Deque[float] = deque(maxlen=100)
        self.volume_history: Deque[float] = deque(maxlen=100)

        # Trade tracking
        self.daily_pnl = 0.0
        self.cooldown_until = 0
        self.trades_today = 0
        self.tick_count = 0

        # Mode
        self.mode = NFIMode(config.mode)

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        """
        NFI decision logic.
        """
        self.tick_count += 1
        current_time = timestamp or int(datetime.now().timestamp())

        # Check cooldown
        if current_time < self.cooldown_until:
            return None

        # Check daily loss
        if self.daily_pnl <= -self.config.max_daily_loss:
            return None

        # Store price data
        mid_price = (bid + ask) / 2
        spread = ask - bid

        self.price_history.append(
            {
                "timestamp": current_time,
                "price": price,
                "bid": bid,
                "ask": ask,
                "mid": mid_price,
                "spread": spread,
            }
        )
        self.close_history.append(mid_price)

        # Need enough history
        if len(self.close_history) < self.config.ema_trend + 5:
            return None

        # Manage existing positions
        action = self._manage_positions(positions, bid, ask, current_time)
        if action:
            return action

        # Check position limit
        if len(positions) >= self.config.max_positions:
            return None

        # Run mode-specific analysis
        return self._analyze_entry(bid, ask, mid_price)

    def _manage_positions(
        self, positions: List[Position], bid: float, ask: float, current_time: int
    ) -> Optional[Dict]:
        """Manage existing positions with trailing stops."""
        for pos in positions:
            profit = 0.0
            if pos.side == PositionSide.LONG:
                profit = bid - pos.entry_price
            else:
                profit = pos.entry_price - ask

            # Check if hit TP
            if pos.tp and profit >= abs(pos.entry_price - pos.tp):
                self._record_trade(profit)
                return {"action": "close", "position_id": pos.id}

            # Check if hit SL
            if pos.sl and profit <= -abs(pos.entry_price - pos.sl):
                self._record_trade(-profit)
                self.cooldown_until = current_time + self.config.cooldown_minutes * 60
                return {"action": "close", "position_id": pos.id}

        return None

    def _analyze_entry(
        self, bid: float, ask: float, mid_price: float
    ) -> Optional[Dict]:
        """Analyze entry conditions based on mode."""

        # Calculate EMAs
        closes = list(self.close_history)

        ema_fast = calculate_ema(closes, self.config.ema_fast)
        ema_medium = calculate_ema(closes, self.config.ema_medium)
        ema_slow = calculate_ema(closes, self.config.ema_slow)
        ema_trend = calculate_ema(closes, self.config.ema_trend)

        if any(x is None for x in [ema_fast, ema_medium, ema_slow, ema_trend]):
            return None

        # Calculate RSI
        rsi = calculate_rsi(closes, self.config.rsi_period)

        # Calculate ATR for TP/SL
        atr = None
        if len(self.high_history) >= self.config.atr_period:
            highs = list(self.high_history)
            lows = list(self.low_history)
            closes_for_atr = list(self.close_history)
            atr = calculate_atr(highs, lows, closes_for_atr, self.config.atr_period)

        # Volume check
        volume_ok = self._check_volume()

        # Mode-specific entry logic
        if self.mode == NFIMode.NORMAL:
            return self._normal_entry(
                bid,
                ask,
                mid_price,
                ema_fast,
                ema_medium,
                ema_slow,
                ema_trend,
                rsi,
                atr,
                volume_ok,
            )
        elif self.mode == NFIMode.PUMP:
            return self._pump_entry(bid, ask, mid_price, rsi, atr)
        elif self.mode == NFIMode.QUICK:
            return self._quick_entry(bid, ask, mid_price, rsi, atr)
        elif self.mode == NFIMode.SCALP:
            return self._scalp_entry(bid, ask, mid_price, rsi)

        return None

    def _normal_entry(
        self,
        bid: float,
        ask: float,
        mid_price: float,
        ema_fast: float,
        ema_medium: float,
        ema_slow: float,
        ema_trend: float,
        rsi: Optional[float],
        atr: Optional[float],
        volume_ok: bool,
    ) -> Optional[Dict]:
        """Normal mode: Trend following with EMA alignment."""

        # Trend alignment: fast > medium > slow
        bullish_trend = ema_fast > ema_medium > ema_slow and mid_price > ema_trend
        bearish_trend = ema_fast < ema_medium < ema_slow and mid_price < ema_trend

        # RSI filter - don't buy at overbought, don't sell at oversold
        rsi_ok_buy = rsi is None or (rsi < self.config.rsi_overbought)
        rsi_ok_sell = rsi is None or (rsi > self.config.rsi_oversold)

        point = self.config.point_value

        if bullish_trend and rsi_ok_buy and volume_ok:
            sl, tp = self._calculate_sl_tp(bid, ask, True, atr)
            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": self.config.lots,
                "sl": sl,
                "tp": tp,
            }

        if bearish_trend and rsi_ok_sell and volume_ok:
            sl, tp = self._calculate_sl_tp(bid, ask, False, atr)
            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": self.config.lots,
                "sl": sl,
                "tp": tp,
            }

        return None

    def _pump_entry(
        self,
        bid: float,
        ask: float,
        mid_price: float,
        rsi: Optional[float],
        atr: Optional[float],
    ) -> Optional[Dict]:
        """Pump mode: Aggressive entries on strong momentum."""

        if len(self.close_history) < 20:
            return None

        closes = list(self.close_history)
        momentum = (closes[-1] - closes[-10]) / closes[-10] if closes[-10] != 0 else 0

        point = self.config.point_value

        # Strong bullish momentum
        if momentum > self.config.pump_momentum_threshold:
            if rsi is None or rsi < 80:  # Allow higher RSI in pump mode
                sl, tp = self._calculate_sl_tp(bid, ask, True, atr)
                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": self.config.lots,
                    "sl": sl,
                    "tp": tp,
                }

        # Strong bearish momentum
        if momentum < -self.config.pump_momentum_threshold:
            if rsi is None or rsi > 20:  # Allow lower RSI in pump mode
                sl, tp = self._calculate_sl_tp(bid, ask, False, atr)
                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": self.config.lots,
                    "sl": sl,
                    "tp": tp,
                }

        return None

    def _quick_entry(
        self,
        bid: float,
        ask: float,
        mid_price: float,
        rsi: Optional[float],
        atr: Optional[float],
    ) -> Optional[Dict]:
        """Quick mode: Quick scalping with tight targets."""

        if rsi is None:
            return None

        point = self.config.point_value

        # Buy on oversold bounce
        if rsi < self.config.rsi_oversold:
            sl = bid - self.config.quick_profit_pips * point
            tp = ask + self.config.quick_profit_pips * point
            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        # Sell on overbought rejection
        if rsi > self.config.rsi_overbought:
            sl = ask + self.config.quick_profit_pips * point
            tp = bid - self.config.quick_profit_pips * point
            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        return None

    def _scalp_entry(
        self, bid: float, ask: float, mid_price: float, rsi: Optional[float]
    ) -> Optional[Dict]:
        """Scalp mode: Ultra-short-term scalping."""

        if rsi is None or len(self.close_history) < 5:
            return None

        closes = list(self.close_history)
        recent_momentum = closes[-1] - closes[-5]
        point = self.config.point_value

        # Buy on slight dip
        if recent_momentum < 0 and rsi < 50:
            sl = bid - self.config.scalp_profit_pips * point
            tp = ask + self.config.scalp_profit_pips * point
            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        # Sell on slight rally
        if recent_momentum > 0 and rsi > 50:
            sl = ask + self.config.scalp_profit_pips * point
            tp = bid - self.config.scalp_profit_pips * point
            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": self.config.lots,
                "sl": round(sl, 2),
                "tp": round(tp, 2),
            }

        return None

    def _calculate_sl_tp(
        self, bid: float, ask: float, is_buy: bool, atr: Optional[float]
    ) -> tuple:
        """Calculate SL and TP based on ATR or fixed values."""
        point = self.config.point_value

        if atr and atr > 0:
            sl_distance = atr * self.config.atr_sl_multiplier
            tp_distance = atr * self.config.atr_tp_multiplier
        else:
            # Default to fixed values
            sl_distance = 10 * point
            tp_distance = 15 * point

        if is_buy:
            sl = bid - sl_distance
            tp = ask + tp_distance
        else:
            sl = ask + sl_distance
            tp = bid - tp_distance

        return round(sl, 2), round(tp, 2)

    def _check_volume(self) -> bool:
        """Check if volume is above average."""
        if len(self.volume_history) < self.config.volume_period:
            return True

        volumes = list(self.volume_history)
        avg_volume = (
            sum(volumes[-self.config.volume_period :]) / self.config.volume_period
        )
        current_volume = volumes[-1] if volumes else 1

        return current_volume >= avg_volume * self.config.volume_multiplier

    def _record_trade(self, profit: float):
        """Record trade result."""
        self.trades_today += 1
        pip_value = self.config.lots * 10
        self.daily_pnl += profit * pip_value

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "mode": self.mode.value,
            "trades_today": self.trades_today,
            "daily_pnl": round(self.daily_pnl, 2),
            "tick_count": self.tick_count,
        }
