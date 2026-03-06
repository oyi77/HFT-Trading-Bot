"""
Trend Following Strategy - EMA Crossover
"""

from typing import Dict, Optional, List

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


class TrendStrategy(Strategy):
    """Simple EMA crossover trend strategy"""
    
    def __init__(self, config):
        super().__init__(config)
        self.prices: List[float] = []
        self.trend = None  # 'up' or 'down'
    
    def on_tick(self, price: float, bid: float, ask: float,
                positions: List[Position], timestamp: int = None) -> Optional[Dict]:
        
        self.prices.append(price)
        if len(self.prices) < 50:
            return None
        
        # Calculate EMAs
        fast_ema = self._ema(self.prices, 20)
        slow_ema = self._ema(self.prices, 50)
        
        prev_trend = self.trend
        self.trend = 'up' if fast_ema > slow_ema else 'down'
        
        if prev_trend == self.trend:
            return None
        
        # Close opposite positions
        for pos in positions:
            if (self.trend == 'up' and pos.side == PositionSide.SHORT) or \
               (self.trend == 'down' and pos.side == PositionSide.LONG):
                return {'action': 'close', 'position_id': pos.id}
        
        # Enter new position
        if self.trend == 'up' and not any(p.side == PositionSide.LONG for p in positions):
            point = self.get_point_value(price)
            sl = price - self.config.stop_loss * point
            return {'action': 'open', 'side': OrderSide.BUY, 'amount': self.config.lots, 'sl': round(sl, 2)}
        
        if self.trend == 'down' and not any(p.side == PositionSide.SHORT for p in positions):
            point = self.get_point_value(price)
            sl = price + self.config.stop_loss * point
            return {'action': 'open', 'side': OrderSide.SELL, 'amount': self.config.lots, 'sl': round(sl, 2)}
        
        return None
    
    def _ema(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return sum(prices) / len(prices)
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = (p - ema) * multiplier + ema
        return ema
