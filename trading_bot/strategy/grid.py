"""
Grid Strategy - Buy low, sell high in a range
Good for ranging markets like XAU during certain periods
"""

from typing import Dict, Optional, List

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


class GridStrategy(Strategy):
    """
    Grid trading strategy
    Places buy orders at lower prices, sell orders at higher prices
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.grid_levels = 5
        self.grid_spacing = 0.005  # 0.5% spacing
        self.base_price = None
        
    def on_tick(self, price: float, bid: float, ask: float,
                positions: List[Position], timestamp: int = None) -> Optional[Dict]:
        
        if self.base_price is None:
            self.base_price = price
        
        # Update base price slowly (trailing center)
        self.base_price = self.base_price * 0.999 + price * 0.001
        
        # Count positions
        longs = sum(1 for p in positions if p.side == PositionSide.LONG)
        shorts = sum(1 for p in positions if p.side == PositionSide.SHORT)
        
        # Find closest grid level
        grid_size = self.base_price * self.grid_spacing
        
        # Check if we should open long (price is below grid level)
        buy_level = self.base_price - grid_size
        if price < buy_level and longs < self.grid_levels:
            sl = price - grid_size * 2
            return {
                'action': 'open',
                'side': OrderSide.BUY,
                'amount': self.config.lots,
                'sl': round(sl, 2),
                'tp': round(self.base_price, 2)  # TP at center
            }
        
        # Check if we should open short (price is above grid level)
        sell_level = self.base_price + grid_size
        if price > sell_level and shorts < self.grid_levels:
            sl = price + grid_size * 2
            return {
                'action': 'open',
                'side': OrderSide.SELL,
                'amount': self.config.lots,
                'sl': round(sl, 2),
                'tp': round(self.base_price, 2)
            }
        
        # Close profitable positions at TP
        for pos in positions:
            if pos.side == PositionSide.LONG and pos.tp > 0 and price >= pos.tp:
                return {'action': 'close', 'position_id': pos.id}
            if pos.side == PositionSide.SHORT and pos.tp > 0 and price <= pos.tp:
                return {'action': 'close', 'position_id': pos.id}
        
        return None
