"""
Exness Exchange - Demo Account Integration for Frontest Mode
Uses Exness Web API for real demo account trading
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExnessPosition:
    """Exness position data - compatible with trading engine"""

    id: str
    symbol: str
    side: str  # buy or sell
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int
    margin: float
    status: str = "open"
    sl: Optional[float] = None
    tp: Optional[float] = None

    @property
    def amount(self) -> float:
        return self.size


class ExnessExchange:
    """
    Exness Exchange wrapper for trading engine
    Uses ExnessWebProvider for real demo account trading
    """

    def __init__(self, account_id: int, token: str, server: str = "trial6"):
        self.account_id = account_id
        self.token = token
        self.server = server
        self.provider = None
        self.connected = False

        # Position tracking
        self.positions: List[ExnessPosition] = []
        self.trades: List[Dict] = []
        self.position_counter: int = 0

        # Balance tracking
        self.balance: float = 0.0
        self.equity: float = 0.0
        self.current_price: float = 0.0

        # Initialize provider
        self._init_provider()

    def _init_provider(self):
        """Initialize Exness Web Provider"""
        try:
            from trading_bot.exchange.exness_web import ExnessWebProvider, ExnessConfig

            config = ExnessConfig(
                account_id=self.account_id, token=self.token, server=self.server
            )
            self.provider = ExnessWebProvider(config)
            logger.info(f"Exness provider initialized for account {self.account_id}")

        except Exception as e:
            logger.error(f"Failed to initialize Exness provider: {e}")
            self.provider = None

    def connect(self) -> bool:
        """Connect to Exness demo account"""
        if not self.provider:
            logger.error("Provider not initialized")
            return False

        try:
            success = self.provider.connect()
            if success:
                # Get initial balance
                self.balance = self.provider.get_balance()
                self.equity = self.provider.get_equity()
                self.connected = True
                logger.info(
                    f"Connected to Exness demo account. Balance: ${self.balance:.2f}"
                )
                return True
            else:
                logger.error("Failed to connect to Exness")
                return False

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        if not self.connected or not self.provider:
            return {"total": 0, "free": 0, "used": 0}

        try:
            self.balance = self.provider.get_balance()
            self.equity = self.provider.get_equity()
            margin_used = (
                self.equity - self.balance if self.equity > self.balance else 0
            )

            return {"total": self.balance, "free": self.balance, "used": margin_used}
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return {"total": 0, "free": 0, "used": 0}

    def get_price(self) -> float:
        """Get current price (for trading engine compatibility)"""
        return self.current_price

    def get_price_with_spread(self, symbol: str = "XAUUSD") -> tuple:
        """Get current price with spread"""
        if not self.provider:
            # Fallback
            base_price = 2650.0
            return base_price - 0.5, base_price + 0.5

        try:
            price = self.provider.get_price(symbol)
            self.current_price = price
            spread = price * 0.0002  # 0.02% spread
            return price - spread, price + spread
        except Exception as e:
            logger.error(f"Price error: {e}")
            return self.current_price - 0.5, self.current_price + 0.5

    def update_price(self):
        """Update current price"""
        if self.provider:
            try:
                price = self.provider.get_price("XAUUSDm")
                self.current_price = price
            except Exception as e:
                logger.debug(f"Failed to update price from Exness: {e}")

    def get_current_price(self) -> float:
        """Get current cached price"""
        return self.current_price

    def open_position(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> Optional[str]:
        """Open a position on Exness demo account"""
        if not self.connected or not self.provider:
            logger.error("Not connected to Exness")
            return None

        try:
            # Convert symbol to Exness format
            exness_symbol = symbol if symbol.endswith("m") else f"{symbol}m"

            # Convert side to Exness format
            exness_side = "long" if side.lower() == "buy" else "short"

            # Get current price
            price = self.provider.get_price(exness_symbol)

            # Open position via provider
            ticket = self.provider.open_position(
                symbol=exness_symbol,
                side=exness_side,
                volume=volume,
                sl=sl,
                tp=tp,
                price=price,
            )

            if ticket:
                logger.info(f"Opened {exness_side} position on Exness: {ticket}")

                # Create local position tracking
                position = ExnessPosition(
                    id=str(ticket),
                    symbol=symbol,
                    side=side.lower(),
                    size=volume,
                    entry_price=price,
                    current_price=price,
                    unrealized_pnl=0,
                    leverage=10,  # Default leverage
                    margin=volume * price / 10,
                    sl=sl,
                    tp=tp,
                )

                self.positions.append(position)
                self.trades.append(
                    {"id": str(ticket), "side": side, "size": volume, "price": price}
                )

                return str(ticket)
            else:
                logger.error("Failed to open position")
                return None

        except Exception as e:
            logger.error(f"Open position error: {e}")
            return None

    def close_position(self, position_id: str) -> Optional[float]:
        """Close a position"""
        if not self.connected or not self.provider:
            return None

        try:
            success = self.provider.close_position(position_id)
            if success:
                # Find position to calculate PnL
                position = next(
                    (p for p in self.positions if p.id == position_id), None
                )
                if position:
                    current_price = self.provider.get_price(position.symbol + "m")
                    if position.side == "buy":
                        pnl = (current_price - position.entry_price) * position.size
                    else:
                        pnl = (position.entry_price - current_price) * position.size

                    # Remove from tracking
                    self.positions = [p for p in self.positions if p.id != position_id]
                    return pnl
            return None

        except Exception as e:
            logger.error(f"Close position error: {e}")
            return None

    def get_positions(self, symbol: str = None) -> List[ExnessPosition]:
        """Get open positions"""
        if not self.provider:
            return []

        try:
            # Fetch from Exness
            exness_positions = self.provider.get_positions()

            # Convert to our format
            self.positions = []
            for pos in exness_positions:
                position = ExnessPosition(
                    id=str(pos.id),
                    symbol=pos.symbol.replace("m", ""),  # Remove 'm' suffix
                    side=pos.side,
                    size=pos.amount,
                    entry_price=pos.entry_price,
                    current_price=pos.entry_price,  # Will be updated
                    unrealized_pnl=pos.unrealized_pnl,
                    leverage=10,
                    margin=pos.amount * pos.entry_price / 10,
                    sl=pos.sl,
                    tp=pos.tp,
                )
                self.positions.append(position)

            if symbol:
                return [p for p in self.positions if p.symbol == symbol]
            return self.positions

        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        if self.provider and self.connected:
            try:
                self.balance = self.provider.get_balance()
                self.equity = self.provider.get_equity()
            except Exception as e:
                logger.debug(f"Failed to fetch live stats: {e}")

        total_pnl = sum(p.unrealized_pnl for p in self.positions)

        return {
            "balance": self.balance,
            "equity": self.equity,
            "positions": len(self.positions),
            "total_pnl": total_pnl,
            "net_pnl": total_pnl,
            "total_trades": len(self.trades),
        }

    def close(self):
        self.connected = False


def create_exness_exchange(
    account_id: int, token: str, server: str = "trial6"
) -> Optional["ExnessExchange"]:
    """Factory function to create Exness exchange"""
    try:
        exchange = ExnessExchange(account_id, token, server)
        if exchange.connect():
            return exchange
    except Exception as e:
        logger.error(f"Failed to create Exness exchange: {e}")

    return None
