"""
Hedging Strategy - Main position + Hedge pending order
"""

from typing import Dict, Optional, List

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


class HedgingStrategy(Strategy):
    """Hedging strategy from original codebase"""
    
    def on_tick(self, price: float, bid: float, ask: float,
                positions: List[Position], timestamp: int = None) -> Optional[Dict]:
        
        point = self.get_point_value(price)
        
        # Trail stops
        self._trail_stops(positions, bid, ask, point)
        
        # Open main position if none
        if not positions:
            return self._open_main(price, bid, ask, point)
        
        return None
    
    def _open_main(self, price: float, bid: float, ask: float, point: float) -> Dict:
        direction = self.config.start_direction
        side = OrderSide.BUY if direction == 0 else OrderSide.SELL
        entry = ask if direction == 0 else bid
        
        sl = entry - self.config.stop_loss * point if direction == 0 else entry + self.config.stop_loss * point
        
        return {
            'action': 'open',
            'side': side,
            'amount': self.config.lots,
            'sl': round(sl, 2)
        }
    
    def _trail_stops(self, positions: List[Position], bid: float, ask: float, point: float):
        """Apply trailing stops"""
        for pos in positions:
            if pos.side == PositionSide.LONG:
                profit = (bid - pos.entry_price) / point
                if profit > self.config.trail_start:
                    new_sl = bid - self.config.trailing * point
                    if new_sl > pos.sl:
                        pos.sl = round(new_sl, 2)
            else:
                profit = (pos.entry_price - ask) / point
                if profit > self.config.trail_start:
                    new_sl = ask + self.config.trailing * point
                    if new_sl < pos.sl or pos.sl == 0:
                        pos.sl = round(new_sl, 2)
