"""
Ostium DEX Exchange - Full SDK Integration
Uses official ostium-python-sdk for real trading on Arbitrum
"""

import asyncio
import importlib
import json
import logging
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

# Try to import Ostium SDK
OstiumSDK: Any = None
NetworkConfig: Any = None
Account: Any = None
try:
    ostium_sdk_module = importlib.import_module("ostium_python_sdk")
    ostium_config_module = importlib.import_module("ostium_python_sdk.config")
    eth_account_module = importlib.import_module("eth_account")

    OstiumSDK = getattr(ostium_sdk_module, "OstiumSDK")
    NetworkConfig = getattr(ostium_config_module, "NetworkConfig")
    Account = getattr(eth_account_module, "Account")

    OSTIUM_SDK_AVAILABLE = True
except Exception:
    OSTIUM_SDK_AVAILABLE = False
    logging.warning("ostium-python-sdk not installed. Ostium trading will not work.")

logger = logging.getLogger(__name__)

# Asset pair mapping for Ostium
# Based on Ostium docs: https://pypi.org/project/ostium-python-sdk/
ASSET_PAIRS = {
    "BTCUSD": {"id": 0, "base": "BTC", "quote": "USD"},
    "BTC/USD": {"id": 0, "base": "BTC", "quote": "USD"},
    "ETHUSD": {"id": 1, "base": "ETH", "quote": "USD"},
    "ETH/USD": {"id": 1, "base": "ETH", "quote": "USD"},
    "EURUSD": {"id": 2, "base": "EUR", "quote": "USD"},
    "XAUUSD": {"id": 5, "base": "XAU", "quote": "USD"},
    "XAU/USD": {"id": 5, "base": "XAU", "quote": "USD"},
    "XAUUSDm": {"id": 5, "base": "XAU", "quote": "USD"},  # Micro gold
    "XAGUSD": {"id": 8, "base": "XAG", "quote": "USD"},
    "SOLUSD": {"id": 9, "base": "SOL", "quote": "USD"},
}


@dataclass
class OstiumPosition:
    """Ostium position data - compatible with trading engine"""

    id: str
    symbol: str
    side: str  # long or short
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int
    liquidation_price: float
    margin: float
    status: str = "open"
    sl: Optional[float] = None
    tp: Optional[float] = None
    pair_id: int = 0
    trade_index: int = 0
    tx_hash: Optional[str] = None

    # Alias for compatibility
    @property
    def amount(self) -> float:
        return self.size


class OstiumExchange:
    """
    Ostium DEX Exchange - Full SDK Integration
    Supports real trading on Arbitrum testnet/mainnet
    """

    def __init__(
        self,
        private_key: str,
        rpc_url: Optional[str] = None,
        chain_id: int = 421614,
        verbose: bool = False,
        leverage: int = 50,
    ):
        if not OSTIUM_SDK_AVAILABLE:
            raise ImportError(
                "ostium-python-sdk is required. Install with: pip install ostium-python-sdk"
            )

        self.private_key = private_key
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.verbose = verbose
        self.leverage = leverage  # Configurable leverage (max 50x for Ostium)
        self.sdk: Optional[Any] = None
        self.connected = False
        self.trader_address: Optional[str] = None
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()

        # Position tracking
        self.positions: List[OstiumPosition] = []
        self.trades: List[Dict] = []
        self.position_counter: int = 0

        # Balance tracking
        self.balance: float = 0.0
        self.equity: float = 0.0
        self.current_price: float = 2650.0
        self._last_successful_price: float = 2650.0
        self._subgraph_warned: bool = False
        self._sdk_price_failed: bool = False
        self._last_synced_position_count: Optional[int] = None

        # Initialize SDK
        self._init_sdk()

    def _init_sdk(self):
        """Initialize Ostium SDK with proper network config"""
        try:
            if not NetworkConfig or not OstiumSDK or not Account:
                raise ImportError("ostium-python-sdk dependencies not available")

            # Set RPC_URL in environment for SDK to use
            import os

            # Auto-detect and fix RPC URL mismatches
            testnet_rpc = "https://sepolia-rollup.arbitrum.io/rpc"
            mainnet_rpc = "https://arb1.arbitrum.io/rpc"

            if self.chain_id == 421614:
                # Using testnet - ensure we use testnet RPC
                if self.rpc_url and (
                    "arb1.arbitrum" in self.rpc_url or "mainnet" in self.rpc_url
                ):
                    logger.warning(
                        f"Mainnet RPC detected with testnet chain_id. Auto-switching to testnet RPC: {testnet_rpc}"
                    )
                    self.rpc_url = testnet_rpc
                elif not self.rpc_url:
                    self.rpc_url = testnet_rpc
            else:
                # Using mainnet
                if not self.rpc_url:
                    self.rpc_url = mainnet_rpc

            if self.rpc_url:
                os.environ["RPC_URL"] = self.rpc_url

            # Use testnet config for frontest mode (chain 421614 = Arbitrum Sepolia)
            if self.chain_id == 421614:
                config = NetworkConfig.testnet()
                logger.info("Using Ostium testnet config (Arbitrum Sepolia)")
            else:
                config = NetworkConfig.mainnet()
                logger.info("Using Ostium mainnet config")

            # Override RPC if provided (after validation)
            if self.rpc_url:
                config.rpc_url = self.rpc_url

            # Initialize SDK
            self.sdk = OstiumSDK(
                config, self.private_key, self.rpc_url, verbose=self.verbose
            )

            # Get trader address
            account = Account.from_key(self.private_key)
            self.trader_address = account.address

            logger.info(f"Ostium SDK initialized. Trader: {self.trader_address}")

        except Exception as e:
            logger.error(f"Failed to initialize Ostium SDK: {e}")
            self.sdk = None
            raise

    async def connect(self) -> bool:
        """Connect to Ostium and verify connection"""
        if not self.sdk:
            logger.error("SDK not initialized")
            return False

        try:
            # Test connection by getting block number or balance
            block_number = self.sdk.w3.eth.block_number
            logger.info(f"Connected to Arbitrum. Block: {block_number}")

            # Get USDC balance
            usdc_balance = await self.get_usdc_balance()
            logger.info(f"USDC Balance: {usdc_balance}")

            self.balance = usdc_balance
            self.equity = (
                usdc_balance  # For now, equity = balance (no unrealized PnL tracking)
            )
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    async def get_usdc_balance(self) -> float:
        """Get USDC balance from SDK"""
        if not self.sdk:
            return 0.0

        try:
            balance = self.sdk.balance.get_usdc_balance(self.trader_address)
            return float(balance)
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return 0.0

    async def get_eth_balance(self) -> float:
        """Get ETH (gas) balance"""
        if not self.sdk:
            return 0.0

        try:
            balance = self.sdk.balance.get_eth_balance(self.trader_address)
            return float(balance)
        except Exception as e:
            logger.error(f"ETH balance error: {e}")
            return 0.0

    def get_balance(self) -> Dict[str, float]:
        """Get balance dict for compatibility with trading engine"""
        return {"total": self.balance, "free": self.balance, "used": 0.0}

    async def get_price(self, symbol: str = "XAUUSD") -> float:
        """Get current price from Ostium oracle"""
        if not self.sdk:
            metadata_price = self._get_metadata_price(symbol)
            if metadata_price is not None:
                self.current_price = metadata_price
                self._last_successful_price = metadata_price
                return metadata_price
            return self._get_static_price(symbol)

        try:
            pair_info = ASSET_PAIRS.get(symbol, ASSET_PAIRS["XAUUSD"])
            base = pair_info["base"]
            quote = pair_info["quote"]

            price, _, _ = await self.sdk.price.get_price(base, quote)
            self.current_price = float(price)
            self._last_successful_price = self.current_price
            self._sdk_price_failed = False
            return self.current_price

        except Exception as e:
            error_str = str(e).lower()
            is_dns_error = any(
                x in error_str
                for x in [
                    "dns",
                    "cannot connect to host",
                    "could not contact",
                    "failed to create dns resolver",
                    "c-ares",
                ]
            )

            if is_dns_error:
                if not self._sdk_price_failed:
                    logger.warning(
                        f"SDK price fetch failed (DNS/network), using fallback: {e}"
                    )
                    self._sdk_price_failed = True
            else:
                logger.error(f"Price error: {e}")

            metadata_price = self._get_metadata_price(symbol)
            if metadata_price is not None:
                self.current_price = metadata_price
                self._last_successful_price = metadata_price
                return metadata_price
            self._last_successful_price = (
                self.current_price
                if self.current_price > 0
                else self._last_successful_price
            )
            return self._last_successful_price

    def _get_metadata_asset(self, symbol: str) -> str:
        mapped = symbol.replace("/", "")
        if mapped == "XAUUSDm":
            return "XAUUSD"
        return mapped

    def _get_metadata_price(self, symbol: str) -> Optional[float]:
        asset = self._get_metadata_asset(symbol)
        query = urllib.parse.urlencode({"asset": asset})
        url = f"https://metadata-backend.ostium.io/PricePublish/latest-price?{query}"

        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if isinstance(payload, dict):
                for key in ("price", "latestPrice", "value"):
                    value = payload.get(key)
                    if value is not None:
                        return float(value)
            return None
        except Exception:
            return None

    def _get_static_price(self, symbol: str) -> float:
        return self._last_successful_price

    def get_price_with_spread(self, symbol: str = "XAUUSD") -> tuple:
        price = self._last_successful_price
        spread = price * 0.0002
        return price - spread, price + spread

    def update_price(self):
        """Update price (called by trading engine)"""
        if not hasattr(self, "_last_successful_price"):
            self._last_successful_price = float(getattr(self, "current_price", 2650.0))

        updated = False
        try:
            price = self._loop.run_until_complete(self.get_price("XAUUSD"))

            if price and price > 0:
                self.current_price = float(price)
                updated = True
        except Exception:
            pass

        if not updated:
            bid, ask = self.get_price_with_spread("XAUUSD")
            self.current_price = (bid + ask) / 2

        for position in getattr(self, "positions", []):
            position.current_price = self.current_price
            if position.side == "long":
                position.unrealized_pnl = (
                    self.current_price - position.entry_price
                ) * position.size
            else:
                position.unrealized_pnl = (
                    position.entry_price - self.current_price
                ) * position.size

        # Update PnL from SDK metrics for accuracy
        self._loop.run_until_complete(self._update_position_pnls_from_sdk())

    async def _update_position_pnls_from_sdk(self):
        sdk = getattr(self, "sdk", None)
        trader_address = getattr(self, "trader_address", None)
        if not sdk or not trader_address:
            return

        for position in getattr(self, "positions", []):
            try:
                metrics = await sdk.get_open_trade_metrics(
                    pair_id=position.pair_id,
                    trade_index=position.trade_index,
                    trader_address=trader_address,
                )
                if metrics and isinstance(metrics, dict):
                    position.unrealized_pnl = float(
                        metrics.get("net_pnl", position.unrealized_pnl)
                    )
                    if metrics.get("liquidation_price"):
                        position.liquidation_price = float(metrics["liquidation_price"])
            except Exception:
                pass

    def get_current_price(self) -> float:
        """Get current cached price"""
        return self.current_price

    async def open_position(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> Optional[str]:
        """Open a real position on Ostium DEX"""
        if not self.sdk or not self.connected:
            logger.error("SDK not connected")
            return None

        try:
            # Get pair info
            pair_info = ASSET_PAIRS.get(symbol)
            if not pair_info:
                logger.error(f"Unknown symbol: {symbol}")
                return None

            pair_id = pair_info["id"]
            # Convert side
            is_long = side.lower() == "buy"
            direction = True if is_long else False
            position_side = "long" if is_long else "short"

            # Get current price
            current_price = await self.get_price(symbol)

            # Calculate collateral (margin)
            # volume is in "lots" - convert to USDC collateral
            # For XAU, 1 unit = $1 of exposure at current price
            leverage = self.leverage
            notional_value = volume * current_price
            collateral = notional_value / leverage

            # Ensure minimum collateral
            if collateral < 10:
                collateral = 10  # Minimum $10

            normalized_order_type = str(order_type).upper()
            if normalized_order_type not in {"MARKET", "LIMIT", "STOP"}:
                normalized_order_type = "MARKET"

            # Prepare trade parameters
            trade_params = {
                "collateral": collateral,
                "leverage": leverage,
                "asset_type": pair_id,
                "direction": direction,
                "order_type": normalized_order_type,
            }

            if hasattr(self.sdk.ostium, "set_slippage_percentage"):
                if normalized_order_type in {"LIMIT", "STOP"}:
                    self.sdk.ostium.set_slippage_percentage(0)
                else:
                    self.sdk.ostium.set_slippage_percentage(1)

            # Add TP/SL if provided - ensure proper distance for Ostium
            # Higher leverage requires wider TP/SL to avoid liquidation
            # Liquidation price = entry_price * (1 +/- 1/leverage)
            # We need TP/SL to be at least 20% beyond liquidation price for safety
            liquidation_pct = 1.0 / leverage  # e.g., 50x = 2%
            min_distance_pct = liquidation_pct * 1.5  # 50% beyond liquidation
            min_distance = current_price * min_distance_pct
            logger.debug(
                f"Using {leverage}x leverage, liquidation at {liquidation_pct:.2%}, min TP/SL distance: {min_distance_pct:.2%}"
            )
            logger.debug(f"Received TP: {tp}, SL: {sl}, Current Price: {current_price}")

            if tp and tp > 0:
                # Validate TP direction: for BUY, TP must be > entry; for SELL, TP must be < entry
                tp_distance = abs(tp - current_price)
                tp_valid_direction = (is_long and tp > current_price) or (
                    not is_long and tp < current_price
                )

                if not tp_valid_direction:
                    logger.debug(
                        f"TP at {tp} is in wrong direction for {position_side} (entry: {current_price}). Skipping TP."
                    )
                    tp = None
                elif tp_distance < min_distance:
                    logger.debug(
                        f"TP at {tp} is too close ({tp_distance:.2f} away, need {min_distance:.2f}). Skipping TP."
                    )
                    tp = None
                else:
                    trade_params["tp"] = float(tp)
                    logger.debug(f"TP set at {tp} ({tp_distance:.2f} away)")

            if sl and sl > 0:
                # Validate SL direction: for BUY, SL must be < entry; for SELL, SL must be > entry
                sl_distance = abs(sl - current_price)
                sl_valid_direction = (is_long and sl < current_price) or (
                    not is_long and sl > current_price
                )

                if not sl_valid_direction:
                    logger.debug(
                        f"SL at {sl} is in wrong direction for {position_side} (entry: {current_price}). Skipping SL."
                    )
                    sl = None
                elif sl_distance < min_distance:
                    logger.debug(
                        f"SL at {sl} is too close ({sl_distance:.2f} away, need {min_distance:.2f}). Skipping SL."
                    )
                    sl = None
                else:
                    trade_params["sl"] = float(sl)
                    logger.debug(f"SL set at {sl} ({sl_distance:.2f} away)")

            logger.info(
                f"Opening {position_side} position on {symbol}: {volume} @ ~{current_price}"
            )
            logger.debug(f"Trade params: {trade_params}")
            logger.debug(
                f"TP in params: {'tp' in trade_params}, SL in params: {'sl' in trade_params}"
            )

            # Execute trade via SDK
            receipt = self.sdk.ostium.perform_trade(
                trade_params, at_price=current_price
            )

            # Handle receipt format - could be dict or object
            if isinstance(receipt, dict):
                tx_hash = receipt.get("transactionHash", "unknown")
                if (
                    tx_hash is not None
                    and not isinstance(tx_hash, str)
                    and hasattr(tx_hash, "hex")
                ):
                    tx_hash = tx_hash.hex()
            else:
                # Receipt might be an object with attributes
                tx_hash = getattr(receipt, "transactionHash", "unknown")
                if (
                    tx_hash is not None
                    and not isinstance(tx_hash, str)
                    and hasattr(tx_hash, "hex")
                ):
                    tx_hash = tx_hash.hex()

            logger.info(f"Trade executed! TX: {tx_hash}")

            # Wait for transaction confirmation
            await asyncio.sleep(5)

            # Get trade details from subgraph
            await self._sync_positions()

            # Find the newly opened trade
            for pos in self.positions:
                if pos.tx_hash == tx_hash or (
                    pos.symbol == symbol and pos.status == "open"
                ):
                    if not any(t.get("tx_hash") == tx_hash for t in self.trades):
                        self.trades.append(
                            {
                                "id": pos.id,
                                "side": side,
                                "size": volume,
                                "price": current_price,
                                "tx_hash": tx_hash,
                            }
                        )
                    logger.info(f"Position opened: {pos.id}")
                    return pos.id

            # If not found in subgraph yet, create local tracking
            self.position_counter += 1
            pos_id = f"pos_{self.position_counter}_{tx_hash[:8]}"

            liquidation = current_price * (0.9 if is_long else 1.1)  # Approx 10x liq

            position = OstiumPosition(
                id=pos_id,
                symbol=symbol,
                side=position_side,
                size=volume,
                entry_price=current_price,
                current_price=current_price,
                unrealized_pnl=0,
                leverage=leverage,
                liquidation_price=liquidation,
                margin=collateral,
                sl=sl,
                tp=tp,
                pair_id=pair_id,
                trade_index=self.position_counter,
                tx_hash=tx_hash,
            )

            self.positions.append(position)
            self.trades.append(
                {
                    "id": pos_id,
                    "side": side,
                    "size": volume,
                    "price": current_price,
                    "tx_hash": tx_hash,
                }
            )

            return pos_id

        except Exception as e:
            logger.error(f"Open position error: {e}")
            return None

    async def close_position(self, position_id: str) -> Optional[float]:
        """Close a position on Ostium DEX"""
        if not self.sdk:
            return None

        try:
            # Find position
            position = next((p for p in self.positions if p.id == position_id), None)
            if not position:
                logger.error(f"Position not found: {position_id}")
                return None

            logger.info(f"Closing position: {position_id}")

            # Close via SDK
            market_price = await self.get_price(position.symbol)
            receipt = self.sdk.ostium.close_trade(
                position.pair_id, position.trade_index, market_price
            )

            tx_hash = "unknown"
            if isinstance(receipt, dict):
                tx_raw = receipt.get("transactionHash") or receipt.get("txHash")
                if (
                    tx_raw is not None
                    and not isinstance(tx_raw, str)
                    and hasattr(tx_raw, "hex")
                ):
                    tx_hash = tx_raw.hex()
                elif tx_raw is not None:
                    tx_hash = str(tx_raw)
            else:
                tx_raw = getattr(receipt, "transactionHash", None) or getattr(
                    receipt, "hash", None
                )
                if (
                    tx_raw is not None
                    and not isinstance(tx_raw, str)
                    and hasattr(tx_raw, "hex")
                ):
                    tx_hash = tx_raw.hex()
                elif tx_raw is not None:
                    tx_hash = str(tx_raw)

            logger.info(f"Position closed! TX: {tx_hash}")

            # Calculate realized PnL
            current_price = market_price
            if position.side == "long":
                pnl = (current_price - position.entry_price) * position.size
            else:
                pnl = (position.entry_price - current_price) * position.size

            # Remove from tracking
            self.positions = [p for p in self.positions if p.id != position_id]

            return pnl

        except Exception as e:
            logger.error(f"Close position error: {e}")
            return None

    async def _sync_positions(self):
        """Sync positions from Ostium subgraph"""
        if not self.sdk or not self.trader_address:
            return

        try:
            open_trades = []
            wrapper_succeeded = False

            # Preferred SDK wrapper path: returns (open_trades, trader_address)
            try:
                wrapped = await self.sdk.get_open_trades(self.trader_address)
                if isinstance(wrapped, tuple):
                    open_trades = wrapped[0] or []
                elif isinstance(wrapped, list):
                    open_trades = wrapped
                wrapper_succeeded = True
            except Exception:
                open_trades = []
                wrapper_succeeded = False

            if not wrapper_succeeded:
                open_trades = await self.sdk.subgraph.get_open_trades(
                    self.trader_address
                )

            # Convert to our format
            self.positions = []
            for idx, trade in enumerate(open_trades):
                pair = trade.get("pair", {})
                pair_id = int(pair.get("id", trade.get("index", 0)))

                # Build symbol from pair
                from_symbol = pair.get("from", "XAU")
                to_symbol = pair.get("to", "USD")
                symbol = f"{from_symbol}{to_symbol}"

                # Map to our symbol format
                if symbol == "XAUUSD":
                    symbol = "XAUUSD"
                elif symbol == "BTCUSD":
                    symbol = "BTCUSD"
                elif symbol == "ETHUSD":
                    symbol = "ETHUSD"

                # Direction
                is_buy = trade.get("isBuy", True)
                side = "long" if is_buy else "short"

                # Parse values with proper decimal conversions
                # collateral, notional: /1e6 (USDC has 6 decimals)
                # prices: /1e18
                # leverage: /100
                collateral = float(trade.get("collateral", 0)) / 1e6
                notional = float(trade.get("notional", 0)) / 1e6
                open_price = float(trade.get("openPrice", 0)) / 1e18
                leverage_raw = float(trade.get("leverage", 1000))
                leverage = leverage_raw / 100 if leverage_raw > 100 else leverage_raw
                if leverage <= 0:
                    leverage = 1.0

                # TP/SL prices
                tp_price = trade.get("takeProfitPrice", "0")
                sl_price = trade.get("stopLossPrice", "0")
                tp = float(tp_price) / 1e18 if tp_price != "0" else None
                sl = float(sl_price) / 1e18 if sl_price != "0" else None

                # Funding
                # Calculate liquidation price (approximate)
                if side == "long":
                    liq_price = open_price * (1 - 1 / leverage)
                else:
                    liq_price = open_price * (1 + 1 / leverage)

                position = OstiumPosition(
                    id=str(trade.get("tradeID", f"trade_{idx}")),
                    symbol=symbol,
                    side=side,
                    size=notional / open_price
                    if open_price > 0
                    else 0,  # Calculate size from notional
                    entry_price=open_price,
                    current_price=open_price,  # Will be updated separately
                    unrealized_pnl=float(trade.get("payout", 0)) / 1e18
                    - collateral,  # Approximate
                    leverage=int(leverage),
                    liquidation_price=liq_price,
                    margin=collateral,
                    sl=sl,
                    tp=tp,
                    pair_id=pair_id,
                    trade_index=int(trade.get("index", idx)),
                )
                self.positions.append(position)

            synced_count = len(self.positions)
            if self._last_synced_position_count != synced_count:
                logger.info(f"Synced {synced_count} positions from Ostium")
                self._last_synced_position_count = synced_count
            self._subgraph_warned = False

        except Exception as e:
            error_text = str(e).lower()
            is_subgraph_404 = "404" in error_text and (
                "not found" in error_text or "goldsky" in error_text
            )

            if is_subgraph_404:
                self._subgraph_warned = False
                return

            if not self._subgraph_warned:
                logger.warning(f"Position sync unavailable on current endpoint: {e}")
                self._subgraph_warned = True

    def get_positions(self, symbol: Optional[str] = None) -> List[OstiumPosition]:
        """Get open positions"""
        if symbol:
            return [p for p in self.positions if p.symbol == symbol]
        return self.positions

    def get_stats(self) -> Dict[str, Any]:
        """Get trading stats"""
        total_pnl = sum(p.unrealized_pnl for p in self.positions)

        return {
            "balance": self.balance,
            "equity": self.balance + total_pnl,
            "positions": len(self.positions),
            "total_pnl": total_pnl,
            "net_pnl": total_pnl,
            "total_trades": len(self.trades),
        }

    def close(self):
        if hasattr(self, "_loop") and not self._loop.is_closed():
            self._loop.close()
        self.connected = False

    async def request_testnet_tokens(self) -> bool:
        """Request USDC tokens from testnet faucet"""
        if not self.sdk:
            return False

        try:
            # Check if we can request
            if self.sdk.faucet.can_request_tokens(self.trader_address):
                amount = self.sdk.faucet.get_token_amount()
                logger.info(f"Requesting {amount} USDC from faucet...")

                receipt = self.sdk.faucet.request_tokens()
                tx_hash = receipt["transactionHash"].hex()
                logger.info(f"Tokens requested! TX: {tx_hash}")

                # Wait and update balance
                await asyncio.sleep(5)
                self.balance = await self.get_usdc_balance()
                return True
            else:
                next_time = self.sdk.faucet.get_next_request_time(self.trader_address)
                logger.info(f"Cannot request tokens yet. Next request: {next_time}")
                return False

        except Exception as e:
            logger.error(f"Faucet error: {e}")
            return False


async def create_ostium_exchange(
    private_key: str,
    rpc_url: Optional[str] = None,
    chain_id: int = 421614,
    verbose: bool = False,
    leverage: int = 50,
) -> Optional[OstiumExchange]:
    """Factory function to create and connect Ostium exchange"""
    if not OSTIUM_SDK_AVAILABLE:
        logger.error("ostium-python-sdk not available")
        return None

    try:
        exchange = OstiumExchange(private_key, rpc_url, chain_id, verbose, leverage)
        if await exchange.connect():
            return exchange
    except Exception as e:
        logger.error(f"Failed to create Ostium exchange: {e}")

    return None
