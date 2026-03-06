"""Abstract async exchange interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

from trading_bot.core.models import Position


class AsyncExchange(ABC):
    """Abstract async exchange for asynchronous provider implementations."""

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        """Return the latest price for a symbol."""

    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Return open positions, optionally filtered by symbol."""

    @abstractmethod
    async def get_balance(self) -> float:
        """Return the current account balance."""

    @abstractmethod
    async def open_position(
        self,
        symbol: str,
        side: str,
        amount: float,
        **kwargs,
    ) -> Optional[str]:
        """Open a new position and return the position ID when successful."""

    @abstractmethod
    async def close_position(self, position_id: str) -> bool:
        """Close a position by ID and return whether it succeeded."""
