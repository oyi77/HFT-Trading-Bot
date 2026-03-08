"""
XAU/USD Hedging Strategy - Optimized for Gold
Based on ahdu.mq5 / halah.mq5 with session awareness
"""

from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class XAUHedgingConfig:
    """Configuration for XAU Hedging Strategy"""

    # Trade parameters
    lots: float = 0.01  # Lot size
    stop_loss: int = 600  # SL in pips (XAU pips = $0.01) - optimized for volatility
    take_profit: int = 1500  # TP in pips (0 = no TP, use trailing) - 1:2.5 ratio

    # Direction: 0 = buy first, 1 = sell first
    start_direction: int = 0

    # Hedge parameters
    x_distance: int = 100  # Distance from SL for hedge

    # Trailing stop
    trail_start: int = 100  # Start trailing after N pips profit
    trailing: int = 50  # Trail distance in pips

    # Break even
    break_even_profit: int = 50  # Move to BE after N pips
    break_even_offset: int = 10  # BE offset in pips

    # Session filter (optional)
    use_session_filter: bool = True  # Enable session filter for better performance

    # Position management
    max_concurrent_positions: int = 2  # Main + 1 hedge max


class XAUHedgingStrategy(Strategy):
    """
    XAU/USD specific hedging strategy

    Key differences from regular hedging:
    - Point value: $0.01 for XAU/USD
    - Session awareness (London/NY are best for gold)
    - Smaller lot sizes (gold is expensive)
    - Tighter stops (gold can move fast)
    """

    def __init__(self, config: XAUHedgingConfig = None):
        if config is None:
            config = XAUHedgingConfig()
        super().__init__(config)
        self.main_position: Optional[Position] = None
        self.session_profits = {"asia": 0, "london": 0, "ny": 0}

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        point = 0.01  # XAU/USD point value

        # Check session (skip if data doesn't have good sessions)
        current_session = self._get_session(timestamp)

        # Apply session filter if enabled
        if self.config.use_session_filter and not self._is_good_session(
            current_session
        ):
            return None

        self._update_tracking(positions)
        self._trail_stops(positions, bid, ask, point)

        # Respect position limits
        if len(positions) >= self.config.max_concurrent_positions:
            return None

        if not positions:
            return self._open_main(price, bid, ask, point)

        if len(positions) == 1:
            return self._handle_hedge(positions[0], bid, ask, point)

        return None

    def _get_session(self, timestamp: int = None) -> str:
        """Get current trading session"""
        if timestamp:
            hour = datetime.utcfromtimestamp(timestamp / 1000).hour
        else:
            hour = datetime.utcnow().hour

        if 0 <= hour < 7:
            return "asia"
        elif 7 <= hour < 12:
            return "london_open"
        elif 12 <= hour < 17:
            return "london_peak"
        elif 17 <= hour < 22:
            return "ny"
        else:
            return "off_market"

    def _is_good_session(self, session: str) -> bool:
        """Check if current session is good for trading gold"""
        # Skip Asia - gold usually ranging/choppy
        # Skip off-market
        good_sessions = ["london_open", "london_peak", "ny"]
        return session in good_sessions

    def _update_tracking(self, positions: List[Position]):
        """Track main position"""
        # Only set main position if we don't already have one
        if not self.main_position and positions:
            self.main_position = positions[0]
        elif not positions:
            self.main_position = None

    def _open_main(self, price: float, bid: float, ask: float, point: float) -> Dict:
        """Open main position - follow trend or use direction"""
        direction = self.config.start_direction
        side = OrderSide.BUY if direction == 0 else OrderSide.SELL
        entry = ask if direction == 0 else bid

        # XAU/USD optimized SL
        sl_distance = self.config.stop_loss * point
        sl = entry - sl_distance if direction == 0 else entry + sl_distance

        # Smaller lots for gold (it's expensive!)
        lots = min(self.config.lots, 0.05)  # Max 0.05 lots for gold

        # Calculate TP if set
        tp = 0
        if self.config.take_profit > 0:
            tp_distance = self.config.take_profit * point
            tp = entry + tp_distance if direction == 0 else entry - tp_distance

        return {
            "action": "open",
            "side": side,
            "amount": lots,
            "sl": round(sl, 2),
            "tp": round(tp, 2) if tp > 0 else 0,
        }

    def _handle_hedge(
        self, main_pos: Position, bid: float, ask: float, point: float
    ) -> Optional[Dict]:
        """Create hedge pending order"""
        if not main_pos.sl:
            return None

        x_dist = self.config.x_distance * point

        if main_pos.side == PositionSide.LONG:
            # Sell stop below SL
            hedge_price = main_pos.sl + x_dist
            # Ensure valid (below current bid)
            if hedge_price > bid - point * 10:
                hedge_price = bid - point * 10 - point
            hedge_sl = hedge_price + self.config.stop_loss * point
            hedge_side = OrderSide.SELL
        else:
            # Buy stop above SL
            hedge_price = main_pos.sl - x_dist
            if hedge_price < ask + point * 10:
                hedge_price = ask + point * 10 + point
            hedge_sl = hedge_price - self.config.stop_loss * point
            hedge_side = OrderSide.BUY

        return {
            "action": "pending",
            "side": hedge_side,
            "amount": main_pos.amount,  # Same size as main
            "stop_price": round(hedge_price, 2),
            "sl": round(hedge_sl, 2),
        }

    def _trail_stops(
        self, positions: List[Position], bid: float, ask: float, point: float
    ):
        """Trailing stop with break-even logic"""
        for pos in positions:
            current_sl = pos.sl if pos.sl is not None else 0
            if pos.side == PositionSide.LONG:
                profit_pts = (bid - pos.entry_price) / point

                # Break even first
                if profit_pts >= self.config.break_even_profit:
                    be_sl = pos.entry_price + self.config.break_even_offset * point
                    if be_sl > current_sl:
                        pos.sl = round(be_sl, 2)
                        current_sl = pos.sl

                # Then trailing
                if profit_pts > self.config.trail_start:
                    new_sl = bid - self.config.trailing * point
                    if new_sl > current_sl:
                        pos.sl = round(new_sl, 2)
                        current_sl = pos.sl

            else:  # SHORT
                profit_pts = (pos.entry_price - ask) / point

                if profit_pts >= self.config.break_even_profit:
                    be_sl = pos.entry_price - self.config.break_even_offset * point
                    if be_sl < current_sl or current_sl == 0:
                        pos.sl = round(be_sl, 2)
                        current_sl = pos.sl

                if profit_pts > self.config.trail_start:
                    new_sl = ask + self.config.trailing * point
                    if new_sl < current_sl or current_sl == 0:
                        pos.sl = round(new_sl, 2)
                        current_sl = pos.sl
