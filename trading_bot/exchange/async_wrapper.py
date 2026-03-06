"""Async wrapper for sync Exchange providers."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from trading_bot.core.models import Position, Balance, OrderSide
from trading_bot.exchange.base import Exchange
from trading_bot.exchange.async_base import AsyncExchange


class AsyncExchangeWrapper(AsyncExchange):
    """Wraps a sync Exchange to implement AsyncExchange interface.

    Uses ThreadPoolExecutor to run blocking sync methods without
    blocking the asyncio event loop.

    Example:
        >>> sync_exchange = PaperTradingExchange()
        >>> async_exchange = AsyncExchangeWrapper(sync_exchange)
        >>> price = await async_exchange.get_price("XAUUSD")
    """

    _executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=4)

    def __init__(self, sync_exchange: Exchange):
        """Initialize wrapper with a sync Exchange instance.

        Args:
            sync_exchange: A synchronous Exchange implementation
        """
        self._sync = sync_exchange

    async def get_price(self, symbol: str) -> float:
        """Get mid-price for symbol.

        Args:
            symbol: Trading symbol (e.g., "XAUUSD")

        Returns:
            Mid-price (average of bid/ask if tuple, direct price if float)
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._sync.get_price)
        # Handle both tuple (bid, ask) and float return types
        if isinstance(result, tuple):
            bid, ask = result
            return (bid + ask) / 2
        return float(result)

    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter positions

        Returns:
            List of Position objects
        """
        loop = asyncio.get_event_loop()
        positions = await loop.run_in_executor(
            self._executor, lambda: self._sync.positions
        )
        if symbol:
            return [p for p in positions if p.symbol == symbol]
        return positions

    async def get_balance(self) -> float:
        """Get account balance.

        Returns:
            Total account balance
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._sync.get_balance)
        # Handle both Balance object and direct float/int return
        if hasattr(result, "total"):
            return float(result.total)
        return float(result)

    async def open_position(
        self,
        symbol: str,
        side: str,
        amount: float,
        **kwargs,
    ) -> Optional[str]:
        """Open a position and return position ID.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            amount: Position size
            **kwargs: Additional order parameters (sl, tp, etc.)

        Returns:
            Position ID if successful, None otherwise
        """
        loop = asyncio.get_event_loop()
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order = await loop.run_in_executor(
            self._executor,
            lambda: self._sync.create_order(order_side, amount, **kwargs),
        )
        return order.id if order else None

    async def close_position(self, position_id: str) -> bool:
        """Close a position by ID.

        Args:
            position_id: ID of position to close

        Returns:
            True if closed successfully, False otherwise
        """
        loop = asyncio.get_event_loop()
        # Find position by ID
        positions = await self.get_positions()
        position = next((p for p in positions if p.id == position_id), None)
        if not position:
            return False
        trade = await loop.run_in_executor(
            self._executor, lambda: self._sync.close_position(position)
        )
        return trade is not None

    async def __aenter__(self) -> "AsyncExchangeWrapper":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        pass
