"""
Abstract exchange interface - canonical Exchange ABC.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from trading_bot.core.models import Order, OrderSide, Position, Trade, Balance, OHLCV


class Exchange(ABC):
    """Abstract exchange - can be real or simulated.

    This is the canonical Exchange interface for all providers.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to exchange. Returns True if successful."""
        pass

    @abstractmethod
    def get_balance(self) -> Balance:
        """Get account balance."""
        pass

    @abstractmethod
    def get_price(self) -> tuple:
        """Get current price. Returns (bid, ask)."""
        pass

    @abstractmethod
    def create_order(
        self,
        side: OrderSide,
        amount: float,
        price: float = 0,
        sl: float = 0,
        tp: float = 0,
    ) -> Optional[Order]:
        """Create a new order."""
        pass

    @abstractmethod
    def close_position(self, position: Position) -> Optional[Trade]:
        """Close a position."""
        pass

    @abstractmethod
    def fetch_ohlcv(self, timeframe: str = "1h", limit: int = 100) -> List[OHLCV]:
        """Fetch historical OHLCV data."""
        pass

    @property
    @abstractmethod
    def positions(self) -> List[Position]:
        """Get open positions."""
        pass

    # Additional methods from core/interfaces.py for compatibility
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """Get open positions as list of dicts. Override for filtering."""
        positions = self.positions
        if symbol:
            return [
                p.__dict__ if hasattr(p, "__dict__") else p
                for p in positions
                if p.symbol == symbol
            ]
        return [p.__dict__ if hasattr(p, "__dict__") else p for p in positions]

    def open_position(
        self, symbol: str, side: str, volume: float, sl: float = None, tp: float = None
    ) -> Optional[str]:
        """Open a position. Returns position ID or None."""
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order = self.create_order(order_side, volume, sl=sl or 0, tp=tp or 0)
        return order.id if order else None

    def modify_position(self, ticket: str, sl: float = None, tp: float = None) -> bool:
        """Modify position SL/TP. Override in subclass."""
        return False

    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        balance = self.get_balance()
        return {
            "balance": balance.total,
            "equity": balance.equity,
            "free": balance.free,
            "used": balance.used,
        }

    def get_candles(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Dict]:
        """Get historical candles. Override in subclass."""
        ohlcv = self.fetch_ohlcv(timeframe, limit)
        return [o.__dict__ if hasattr(o, "__dict__") else o for o in ohlcv]
