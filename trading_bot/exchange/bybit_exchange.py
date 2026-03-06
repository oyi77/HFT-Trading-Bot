"""
Bybit Exchange - Testnet Integration for Frontest Mode
Uses CCXT with Bybit testnet for real demo trading
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BybitPosition:
    """Bybit position data - compatible with trading engine"""

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


class BybitExchange:
    """
    Bybit Exchange wrapper for trading engine
    Uses CCXT with Bybit testnet for real demo trading
    """

    def __init__(
        self, api_key: str, api_secret: str, testnet: bool = True, leverage: int = 10
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.leverage = leverage
        self.exchange = None
        self.connected = False

        # Position tracking
        self.positions: List[BybitPosition] = []
        self.trades: List[Dict] = []
        self.position_counter: int = 0

        # Balance tracking
        self.balance: float = 0.0
        self.equity: float = 0.0
        self.current_price: float = 0.0

        # Initialize CCXT
        self._init_ccxt()

    def _init_ccxt(self):
        """Initialize CCXT Bybit exchange"""
        try:
            import ccxt

            self.exchange = ccxt.bybit(
                {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "swap",
                    },
                }
            )

            # Enable testnet
            if self.testnet:
                self.exchange.set_sandbox_mode(True)
                logger.info("Bybit testnet mode enabled")

            logger.info("Bybit CCXT exchange initialized")

        except ImportError:
            logger.error("CCXT not installed. Install with: pip install ccxt")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Bybit: {e}")
            self.exchange = None

    def connect(self) -> bool:
        """Connect to Bybit and verify credentials"""
        if not self.exchange:
            logger.error("Exchange not initialized")
            return False

        try:
            # Load markets to verify connection
            self.exchange.load_markets()

            # Get balance to verify credentials
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get("USDT", {}).get("free", 0)

            self.balance = float(usdt_balance) if usdt_balance else 0.0
            self.equity = self.balance
            self.connected = True

            network = "testnet" if self.testnet else "mainnet"
            logger.info(f"Connected to Bybit {network}. Balance: {self.balance} USDT")
            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        if not self.connected or not self.exchange:
            return {"total": 0, "free": 0, "used": 0}

        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get("USDT", {})

            total = float(usdt.get("total", 0))
            free = float(usdt.get("free", 0))
            used = float(usdt.get("used", 0))

            self.balance = free

            return {"total": total, "free": free, "used": used}
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return {"total": 0, "free": 0, "used": 0}

    def get_price(self) -> float:
        """Get current price"""
        return self.current_price

    def get_price_with_spread(self, symbol: str = "XAUUSD") -> tuple:
        """Get current price with spread"""
        if not self.exchange:
            base_price = 2650.0
            return base_price - 0.5, base_price + 0.5

        try:
            # Convert symbol to Bybit format
            bybit_symbol = self._convert_symbol(symbol)

            ticker = self.exchange.fetch_ticker(bybit_symbol)
            bid = float(ticker.get("bid", 0))
            ask = float(ticker.get("ask", 0))

            if bid == 0 or ask == 0:
                # Fallback to last price
                last = float(ticker.get("last", 2650.0))
                spread = last * 0.0002
                bid = last - spread
                ask = last + spread

            self.current_price = (bid + ask) / 2
            return bid, ask

        except Exception as e:
            logger.error(f"Price error: {e}")
            return self.current_price - 0.5, self.current_price + 0.5

    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol to Bybit format"""
        # XAUUSD -> XAUUSDT
        symbol_mapping = {
            "XAUUSD": "XAUT/USDT:USDT",
            "XAU/USD": "XAUT/USDT:USDT",
            "XAUUSDm": "XAUT/USDT:USDT",
            "BTCUSD": "BTC/USDT:USDT",
            "BTC/USD": "BTC/USDT:USDT",
            "ETHUSD": "ETH/USDT:USDT",
            "ETH/USD": "ETH/USDT:USDT",
        }
        if symbol in symbol_mapping:
            return symbol_mapping[symbol]

        base = symbol.replace("/", "").replace("USD", "")
        return f"{base}/USDT:USDT"

    def update_price(self):
        """Update current price"""
        self.get_price_with_spread("XAUUSD")

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
        """Open a position on Bybit"""
        if not self.connected or not self.exchange:
            logger.error("Not connected to Bybit")
            return None

        try:
            bybit_symbol = self._convert_symbol(symbol)

            # Convert side
            bybit_side = "buy" if side.lower() == "buy" else "sell"

            # Get current price
            bid, ask = self.get_price_with_spread(symbol)
            entry_price = ask if bybit_side == "buy" else bid

            amount = float(self.exchange.amount_to_precision(bybit_symbol, volume))

            try:
                self.exchange.set_leverage(self.leverage, bybit_symbol)
            except Exception:
                pass

            order = self.exchange.create_order(
                bybit_symbol,
                "market",
                bybit_side,
                amount,
                params={"reduceOnly": False},
            )

            if order:
                order_id = order.get("id", f"order_{self.position_counter}")
                logger.info(f"Opened {bybit_side} position on Bybit: {order_id}")

                # Create local position tracking
                self.position_counter += 1
                pos_id = f"pos_{self.position_counter}_{order_id}"

                # Calculate liquidation (approx 10x leverage)
                if bybit_side == "buy":
                    liq_price = entry_price * 0.9
                else:
                    liq_price = entry_price * 1.1

                position = BybitPosition(
                    id=pos_id,
                    symbol=symbol,
                    side=bybit_side,
                    size=volume,
                    entry_price=entry_price,
                    current_price=entry_price,
                    unrealized_pnl=0,
                    leverage=self.leverage,
                    margin=(amount * entry_price) / self.leverage,
                    sl=sl,
                    tp=tp,
                )

                self.positions.append(position)
                self.trades.append(
                    {"id": pos_id, "side": side, "size": volume, "price": entry_price}
                )

                return pos_id
            else:
                logger.error("Failed to create order")
                return None

        except Exception as e:
            logger.error(f"Open position error: {e}")
            return None

    def close_position(self, position_id: str) -> Optional[float]:
        """Close a position"""
        if not self.connected or not self.exchange:
            return None

        try:
            position = next((p for p in self.positions if p.id == position_id), None)
            if not position:
                logger.error(f"Position not found: {position_id}")
                return None

            bybit_symbol = self._convert_symbol(position.symbol)

            # Get current price
            bid, ask = self.get_price_with_spread(position.symbol)
            exit_price = bid if position.side == "buy" else ask

            # Close position (market order opposite side)
            close_side = "sell" if position.side == "buy" else "buy"
            close_amount = float(
                self.exchange.amount_to_precision(bybit_symbol, position.size)
            )

            order = self.exchange.create_order(
                bybit_symbol,
                "market",
                close_side,
                close_amount,
                params={"reduceOnly": True},
            )

            if order:
                # Calculate PnL
                if position.side == "buy":
                    pnl = (exit_price - position.entry_price) * position.size
                else:
                    pnl = (position.entry_price - exit_price) * position.size

                # Remove from tracking
                self.positions = [p for p in self.positions if p.id != position_id]

                logger.info(f"Closed position: {position_id}, PnL: {pnl}")
                return pnl

            return None

        except Exception as e:
            logger.error(f"Close position error: {e}")
            return None

    def get_positions(self, symbol: str = None) -> List[BybitPosition]:
        """Get open positions"""
        if not self.exchange:
            return []

        try:
            # Fetch from Bybit
            positions = self.exchange.fetch_positions()

            # Update local tracking
            self.positions = []
            for pos in positions:
                if float(pos.get("contracts", 0)) == 0:
                    continue

                bybit_symbol = pos.get("symbol", "")
                base_symbol = bybit_symbol.replace("USDT", "").replace("/", "")

                position = BybitPosition(
                    id=str(pos.get("id", f"pos_{len(self.positions)}")),
                    symbol=base_symbol,
                    side=pos.get("side", "buy"),
                    size=float(pos.get("contracts", 0)),
                    entry_price=float(pos.get("entryPrice", 0)),
                    current_price=float(pos.get("markPrice", 0)),
                    unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                    leverage=int(pos.get("leverage", 10)),
                    margin=float(pos.get("initialMargin", 0)),
                    sl=float(pos.get("stopLoss", 0)) if pos.get("stopLoss") else None,
                    tp=float(pos.get("takeProfit", 0))
                    if pos.get("takeProfit")
                    else None,
                )
                self.positions.append(position)

            if symbol:
                return [p for p in self.positions if p.symbol == symbol]
            return self.positions

        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get trading stats"""
        total_pnl = sum(p.unrealized_pnl for p in self.positions)

        return {
            "balance": self.balance,
            "equity": self.balance + total_pnl,
            "positions": len(self.positions),
            "total_pnl": total_pnl,
            "total_trades": len(self.trades),
        }

    def close(self):
        self.connected = False
        if self.exchange and hasattr(self.exchange, "close"):
            try:
                self.exchange.close()
            except Exception:
                pass


def create_bybit_exchange(
    api_key: str, api_secret: str, testnet: bool = True, leverage: int = 10
) -> Optional["BybitExchange"]:
    """Factory function to create Bybit exchange"""
    try:
        exchange = BybitExchange(api_key, api_secret, testnet, leverage)
        if exchange.connect():
            return exchange
    except Exception as e:
        logger.error(f"Failed to create Bybit exchange: {e}")

    return None
