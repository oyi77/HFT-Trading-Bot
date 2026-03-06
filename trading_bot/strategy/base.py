"""
Abstract strategy interface
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List

from trading_bot.core.models import Position, OrderSide


class Strategy(ABC):
    """Base class for all strategies"""
    
    def __init__(self, config):
        self.config = config
    
    @abstractmethod
    def on_tick(self, price: float, bid: float, ask: float, 
                positions: List[Position], timestamp: int = None) -> Optional[Dict]:
        """
        Returns action dict or None:
        {'action': 'open', 'side': OrderSide.BUY, 'amount': 0.1, 'sl': 50000}
        {'action': 'close', 'position_id': 'pos_1'}
        """
        pass
    
    def get_point_value(self, price: float) -> float:
        return 0.0001 if price < 100 else 0.01
