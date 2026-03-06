"""Abstract async exchange interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from trading_bot.core.models import Position


@dataclass
class MarketSnapshot:
    """Combined market data snapshot."""

    price: float
    positions: List[Position]
    balance: float


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

    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """Fetch price, positions, and balance in parallel.

        Default implementation uses asyncio.gather for parallel fetch.
        Subclasses may override for provider-specific optimizations.
        """
        import asyncio

        price, positions, balance = await asyncio.gather(
            self.get_price(symbol),
            self.get_positions(symbol),
            self.get_balance(),
        )
        return MarketSnapshot(
            price=price,
            positions=positions,
            balance=balance,
        )
