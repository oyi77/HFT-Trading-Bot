"""
Abstract exchange interface
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from trading_bot.core.models import (
    Order, OrderSide, Position, Trade, Balance, OHLCV
)


class Exchange(ABC):
    """Abstract exchange - can be real or simulated"""
    
    @abstractmethod
    def connect(self) -> bool:
        pass
    
    @abstractmethod
    def get_balance(self) -> Balance:
        pass
    
    @abstractmethod
    def get_price(self) -> tuple:
        """Returns (bid, ask)"""
        pass
    
    @abstractmethod
    def create_order(self, side: OrderSide, amount: float, 
                     price: float = 0, sl: float = 0, tp: float = 0) -> Optional[Order]:
        pass
    
    @abstractmethod
    def close_position(self, position: Position) -> Optional[Trade]:
        pass
    
    @abstractmethod
    def fetch_ohlcv(self, timeframe: str = "1h", limit: int = 100) -> List[OHLCV]:
        pass
    
    @property
    @abstractmethod
    def positions(self) -> List[Position]:
        pass
