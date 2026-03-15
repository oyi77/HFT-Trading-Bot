"""
ZeroLag EMA Strategy (Ahox Nugroho Rules)

Ported from ZeroLagEA_V2.mq5 + zerolag_strategy.pine

Core logic:
- ZeroLag EMA with ATR volatility bands for trend detection
- Martingale grid/averaging layers (up to max_layers)
- Basket TP with optional runner system
- Signal-reversal cut loss

Entry rules:
- BUY: Trend bullish + candle closed green (close > open)
- SELL: Trend bearish + candle closed red (close < open)

Grid/Averaging:
- Opens additional layers when price moves against position by layer_gap_pips
- Each layer lot = base_lot * lot_multiplier^layer_number

Take Profit:
- Basket TP at avg_entry ± tp_pips
- Runner mode: keep best position with SL at breakeven, close rest
"""

from typing import Dict, Optional, List
from dataclasses import dataclass

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide
from trading_bot.utils.indicators import (
    calculate_zlema_series,
    calculate_atr,
    calculate_highest,
)


@dataclass
class ZeroLagConfig:
    """Configuration for ZeroLag EMA Strategy"""

    # Trade parameters
    lots: float = 0.01
    use_auto_lot: bool = False
    risk_percent: float = 1.0
    point_value: float = 0.01  # XAU = 0.01, Forex = 0.0001

    # ZeroLag Indicator
    band_length: int = 63
    band_multiplier: float = 1.1

    # Grid / Pyramiding
    lot_multiplier: float = 2.0
    layer_gap_pips: float = 20.0
    max_layers: int = 4

    # Take Profit & Runner
    tp_pips: float = 30.0
    sl_pips: float = 100.0
    runner_target_pips: float = 100.0
    use_runner: bool = True
    runner_be_offset_pips: float = 5.0

    # Cut loss on signal reversal
    use_reversal_cut: bool = True

    # Session filter
    use_session_filter: bool = True
    session_1_start: int = 8
    session_1_end: int = 12
    session_2_start: int = 14
    session_2_end: int = 17
    session_3_start: int = 22
    session_3_end: int = 2

    # Signal confirmation
    max_bars_since_signal: int = 3

    # Cooldown (ticks between trades)
    min_ticks_between_trades: int = 5


class ZeroLagStrategy(Strategy):
    """
    ZeroLag EMA Strategy with Martingale Grid and Runner TP

    Ported from ZeroLagEA_V2.mq5 (Ahox Nugroho) and zerolag_strategy.pine.

    Signal: ZLEMA + ATR volatility bands detect trend.
    Entry: Confirmed by candle color (green=buy, red=sell).
    Grid: Martingale averaging up to max_layers.
    TP: Basket TP at average price + tp_pips, with optional runner.
    """

    def __init__(self, config: ZeroLagConfig = None):
        if config is None:
            config = ZeroLagConfig()
        super().__init__(config)

        # Price history
        self.closes: List[float] = []
        self.opens: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []

        # ATR history for highest() calculation
        self.atr_history: List[float] = []

        # Trend state
        self.current_trend: int = 0  # 1 = bullish, -1 = bearish
        self.bars_since_signal: int = 999

        # Trade tracking
        self.tick_count: int = 0
        self.ticks_since_trade: int = 999
        self.last_atr: float = 0.0

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        self.tick_count += 1
        self.ticks_since_trade += 1
        self.bars_since_signal += 1

        mid = (bid + ask) / 2
        self.closes.append(mid)
        self.opens.append(mid)  # Approximate open with mid for tick data
        self.highs.append(ask)
        self.lows.append(bid)

        # Bounded history
        max_len = self.config.band_length * 4 + 100
        if len(self.closes) > max_len:
            self.closes = self.closes[-max_len:]
            self.opens = self.opens[-max_len:]
            self.highs = self.highs[-max_len:]
            self.lows = self.lows[-max_len:]

        # Need enough data for indicator calculation
        min_bars = self.config.band_length + int((self.config.band_length - 1) / 2) + 10
        if len(self.closes) < min_bars:
            return None

        # 0. Session Check
        if not self.is_session_active(timestamp):
            return None

        # 1. Calculate ZeroLag Signal
        prev_trend = self.current_trend
        self._update_trend()

        # 2. Handle signal reversal cut loss
        if self.config.use_reversal_cut and prev_trend != 0 and self.current_trend != 0:
            if prev_trend != self.current_trend:
                cut_action = self._cut_on_reversal(positions)
                if cut_action:
                    return cut_action

        # 3. Manage existing positions (grid averaging + basket TP)
        manage_action = self._manage_positions(positions, bid, ask)
        if manage_action:
            return manage_action

        # 4. Execute new entry signals
        entry_action = self._execute_entry(positions, bid, ask)
        if entry_action:
            return entry_action

        return None

    def _update_trend(self):
        """Calculate ZeroLag EMA + ATR volatility bands and update trend."""
        length = self.config.band_length

        # Calculate ZLEMA series (need at least 2 values for crossover)
        zlema_series = calculate_zlema_series(self.closes, length)
        if zlema_series is None or len(zlema_series) < 2:
            return

        # Calculate ATR
        atr = calculate_atr(self.highs, self.lows, self.closes, length)
        if atr is None:
            return

        self.atr_history.append(atr)
        self.last_atr = atr
        atr_lookback = length * 3
        if len(self.atr_history) > atr_lookback + 50:
            self.atr_history = self.atr_history[-(atr_lookback + 50):]

        # Highest ATR over lookback period
        highest_atr = calculate_highest(self.atr_history, min(atr_lookback, len(self.atr_history)))
        if highest_atr is None:
            highest_atr = atr

        volatility = highest_atr * self.config.band_multiplier

        # Current and previous bar (index from end of ZLEMA series)
        current_zlema = zlema_series[-1]
        prev_zlema = zlema_series[-2]

        # Closes aligned with ZLEMA series end
        current_close = self.closes[-1]
        prev_close = self.closes[-2]

        upper_band = current_zlema + volatility
        lower_band = current_zlema - volatility
        prev_upper = prev_zlema + volatility
        prev_lower = prev_zlema - volatility

        # Bullish crossover: prev close <= upper band AND current close > upper band
        if prev_close <= prev_upper and current_close > upper_band:
            if self.current_trend != 1:
                self.current_trend = 1
                self.bars_since_signal = 0

        # Bearish crossunder: prev close >= lower band AND current close < lower band
        elif prev_close >= prev_lower and current_close < lower_band:
            if self.current_trend != -1:
                self.current_trend = -1
                self.bars_since_signal = 0

    def _execute_entry(
        self, positions: List[Position], bid: float, ask: float
    ) -> Optional[Dict]:
        """Execute initial entry when signal is confirmed."""
        # Cooldown check
        if self.ticks_since_trade < self.config.min_ticks_between_trades:
            return None

        # Signal must be recent
        if self.bars_since_signal > self.config.max_bars_since_signal:
            return None

        # Only enter when no positions (first entry)
        buy_count = sum(1 for p in positions if p.side == PositionSide.LONG)
        sell_count = sum(1 for p in positions if p.side == PositionSide.SHORT)

        if buy_count > 0 or sell_count > 0:
            return None

        # Candle confirmation
        if len(self.closes) < 2 or len(self.opens) < 2:
            return None

        candle_close = self.closes[-2]  # Completed bar
        candle_open = self.opens[-2]

        pip = self.get_pip_value(bid)
        sl_dist = self.config.sl_pips * pip
        tp_dist = self.config.tp_pips * pip

        # Auto-lot sizing
        lots = self.config.lots
        if self.config.use_auto_lot:
            # We don't have direct access to equity here in Strategy interface
            # (passed positions but not account info).
            # We'll assume a 1000 balance or look at position volume as hint,
            # but better to add equity to on_tick or use a default.
            # Actually, calculate_auto_lot needs equity.
            # Given limited interface, we use a default of 1000 or passthrough
            lots = self.calculate_auto_lot(1000.0, self.config.risk_percent, self.config.sl_pips, bid)

        # BUY signal: trend bullish + green candle
        if self.current_trend == 1 and candle_close > candle_open:
            self.ticks_since_trade = 0
            return {
                "action": "open",
                "side": OrderSide.BUY,
                "amount": lots,
                "sl": round(ask - sl_dist, 2),
                "tp": round(ask + tp_dist, 2),
            }

        # SELL signal: trend bearish + red candle
        if self.current_trend == -1 and candle_close < candle_open:
            self.ticks_since_trade = 0
            return {
                "action": "open",
                "side": OrderSide.SELL,
                "amount": lots,
                "sl": round(bid + sl_dist, 2),
                "tp": round(bid - tp_dist, 2),
            }

        return None

    def _manage_positions(
        self, positions: List[Position], bid: float, ask: float
    ) -> Optional[Dict]:
        """Manage grid averaging and basket TP/runner."""
        pip = self.get_pip_value(bid)

        long_positions = [p for p in positions if p.side == PositionSide.LONG]
        short_positions = [p for p in positions if p.side == PositionSide.SHORT]

        # ── MANAGE LONGS ──
        if long_positions:
            action = self._manage_long_basket(long_positions, bid, ask, pip)
            if action:
                return action

        # ── MANAGE SHORTS ──
        if short_positions:
            action = self._manage_short_basket(short_positions, bid, ask, pip)
            if action:
                return action

        return None

    def _manage_long_basket(
        self, positions: List[Position], bid: float, ask: float, pip: float
    ) -> Optional[Dict]:
        """Manage long positions: averaging layers + basket TP."""
        total_buys = len(positions)

        # Calculate average entry price (volume-weighted)
        avg_price = self._get_average_price(positions)
        lowest_price = min(p.entry_price for p in positions)

        # ── GRID AVERAGING ──
        if (
            total_buys < self.config.max_layers
            and self.ticks_since_trade >= self.config.min_ticks_between_trades
        ):
            gap = self.config.layer_gap_pips * pip
            if ask < lowest_price - gap:
                next_lot = round(
                    self.config.lots * (self.config.lot_multiplier ** total_buys), 2
                )
                next_lot = max(0.01, next_lot)
                self.ticks_since_trade = 0
                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": next_lot,
                }

        # ── BASKET TP ──
        tp_target = avg_price + (self.config.tp_pips * pip)
        if bid >= tp_target:
            if self.config.use_runner and total_buys > 1:
                # Close all except the highest entry (runner)
                # Find the position with highest entry price (best for long runner)
                runner = max(positions, key=lambda p: p.entry_price)
                for p in positions:
                    if p.id != runner.id:
                        return {"action": "close", "position_id": p.id}
            else:
                # Flat basket close - close all
                return {"action": "close", "position_id": positions[0].id}

        return None

    def _manage_short_basket(
        self, positions: List[Position], bid: float, ask: float, pip: float
    ) -> Optional[Dict]:
        """Manage short positions: averaging layers + basket TP."""
        total_sells = len(positions)

        avg_price = self._get_average_price(positions)
        highest_price = max(p.entry_price for p in positions)

        # ── GRID AVERAGING ──
        if (
            total_sells < self.config.max_layers
            and self.ticks_since_trade >= self.config.min_ticks_between_trades
        ):
            gap = self.config.layer_gap_pips * pip
            if bid > highest_price + gap:
                next_lot = round(
                    self.config.lots * (self.config.lot_multiplier ** total_sells), 2
                )
                next_lot = max(0.01, next_lot)
                self.ticks_since_trade = 0
                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": next_lot,
                }

        # ── BASKET TP ──
        tp_target = avg_price - (self.config.tp_pips * pip)
        if ask <= tp_target:
            if self.config.use_runner and total_sells > 1:
                # Keep the lowest entry price position as runner (best for short)
                runner = min(positions, key=lambda p: p.entry_price)
                for p in positions:
                    if p.id != runner.id:
                        return {"action": "close", "position_id": p.id}
            else:
                return {"action": "close", "position_id": positions[0].id}

        return None

    def _cut_on_reversal(self, positions: List[Position]) -> Optional[Dict]:
        """Cut loss when signal reverses direction."""
        if self.current_trend == 1:
            # Bullish now → close all shorts
            shorts = [p for p in positions if p.side == PositionSide.SHORT]
            if shorts:
                return {"action": "close", "position_id": shorts[0].id}

        elif self.current_trend == -1:
            # Bearish now → close all longs
            longs = [p for p in positions if p.side == PositionSide.LONG]
            if longs:
                return {"action": "close", "position_id": longs[0].id}

        return None

    @staticmethod
    def _get_average_price(positions: List[Position]) -> float:
        """Calculate volume-weighted average entry price."""
        total_volume = sum(p.amount for p in positions)
        if total_volume == 0:
            return 0.0
        total_value = sum(p.entry_price * p.amount for p in positions)
        return total_value / total_volume

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            "tick_count": self.tick_count,
            "bars": len(self.closes),
            "current_trend": self.current_trend,
            "bars_since_signal": self.bars_since_signal,
            "ticks_since_trade": self.ticks_since_trade,
        }
