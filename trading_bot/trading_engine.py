"""
Trading Engine - Core trading logic that works with any interface
"""

import time
import threading
import os
import asyncio
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from trading_bot.exchange.simulator import SimulatorExchange
from trading_bot.exchange.ostium import OstiumExchange, create_ostium_exchange
from trading_bot.exchange.exness_exchange import ExnessExchange, create_exness_exchange
from trading_bot.exchange.bybit_exchange import BybitExchange, create_bybit_exchange
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.interface.base import InterfaceConfig
from trading_bot.risk.circuit_breaker import CircuitBreaker, CircuitBreakerError

# Type alias for exchanges
ExchangeType = Union[SimulatorExchange, OstiumExchange, ExnessExchange, BybitExchange]


@dataclass
class TradingMetrics:
    """Current trading metrics"""

    price: float = 0.0
    balance: float = 0.0
    equity: float = 0.0
    pnl: float = 0.0
    trades: int = 0
    positions: Optional[List] = None

    def __post_init__(self):
        if self.positions is None:
            self.positions = []

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "balance": self.balance,
            "equity": self.equity,
            "pnl": self.pnl,
            "trades": self.trades,
            "positions": self.positions,
        }


class TradingEngine:
    """
    Trading Engine - handles all trading logic
    Works with any interface (CLI, TUI, Web)
    """

    def __init__(self, config: InterfaceConfig, interface=None):
        self.config = config
        self.interface = interface

        self.running = False
        self.paused = False
        self._stopped = False
        self.thread: Optional[threading.Thread] = None

        # Trading components
        self.exchange: Optional[ExchangeType] = None
        self.strategy: Optional[XAUHedgingStrategy] = None

        # Risk management
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60.0, name="exchange_api"
        )

        # Metrics
        self.metrics = TradingMetrics()

    def initialize(self) -> bool:
        """Initialize trading components"""
        try:
            # Create exchange based on provider and mode
            if self.config.provider == "ostium" and self.config.mode in (
                "frontest",
                "real",
            ):
                # Use real Ostium exchange
                private_key = os.getenv("OSTIUM_PRIVATE_KEY")
                rpc_url = os.getenv(
                    "OSTIUM_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc"
                )
                chain_id = int(os.getenv("OSTIUM_CHAIN_ID", "421614"))

                if not private_key:
                    if self.interface:
                        self.interface.log("OSTIUM_PRIVATE_KEY not found", "error")
                    return False

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                ostium = loop.run_until_complete(
                    create_ostium_exchange(
                        private_key,
                        rpc_url,
                        chain_id,
                        leverage=min(self.config.leverage, 50),
                    )
                )

                if not ostium:
                    if self.interface:
                        self.interface.log("Failed to connect to Ostium", "error")
                    return False

                self.exchange = ostium

                if self.interface:
                    self.interface.log("Connected to Ostium DEX", "info")

            elif self.config.provider == "exness" and self.config.mode == "frontest":
                account_id = os.getenv("EXNESS_ACCOUNT_ID")
                token = os.getenv("EXNESS_TOKEN")
                server = os.getenv("EXNESS_SERVER", "trial6")

                if not account_id or not token:
                    if self.interface:
                        self.interface.log(
                            "EXNESS_ACCOUNT_ID and EXNESS_TOKEN required for frontest",
                            "error",
                        )
                    return False

                exness = create_exness_exchange(
                    account_id=int(account_id), token=token, server=server
                )

                if not exness:
                    if self.interface:
                        self.interface.log("Failed to connect to Exness demo", "error")
                    return False

                self.exchange = exness

                if self.interface:
                    self.interface.log(f"Connected to Exness Demo: {server}", "info")

            elif self.config.provider == "bybit" and self.config.mode == "frontest":
                api_key = os.getenv("BYBIT_API_KEY")
                api_secret = os.getenv("BYBIT_API_SECRET")

                if not api_key or not api_secret:
                    if self.interface:
                        self.interface.log(
                            "BYBIT_API_KEY and BYBIT_API_SECRET required for frontest",
                            "error",
                        )
                    return False

                bybit = create_bybit_exchange(
                    api_key,
                    api_secret,
                    testnet=True,
                    leverage=self.config.leverage,
                )

                if not bybit:
                    if self.interface:
                        self.interface.log(
                            "Failed to connect to Bybit testnet", "error"
                        )
                    return False

                self.exchange = bybit

                if self.interface:
                    self.interface.log("Connected to Bybit Testnet", "info")

            elif self.config.mode == "paper":
                # Use simulator for paper trading
                self.exchange = SimulatorExchange(
                    initial_balance=self.config.balance, symbol=self.config.symbol
                )
            else:
                # Use simulator for other frontest (Exness demo, CCXT testnet)
                self.exchange = SimulatorExchange(
                    initial_balance=self.config.balance, symbol=self.config.symbol
                )

            # Create strategy
            strategy_config = XAUHedgingConfig(
                lots=self.config.lot,
                stop_loss=int(self.config.sl_pips),
                take_profit=int(self.config.tp_pips),
            )
            self.strategy = XAUHedgingStrategy(strategy_config)

            if isinstance(
                self.exchange, (OstiumExchange, ExnessExchange, BybitExchange)
            ):
                self.metrics.balance = self.exchange.balance
                self.metrics.equity = self.exchange.equity
                display_balance = self.exchange.balance
            else:
                self.metrics.balance = self.config.balance
                self.metrics.equity = self.config.balance
                display_balance = self.config.balance

            if self.interface:
                self.interface.log("Trading engine initialized", "info")
                self.interface.log(f"Mode: {self.config.mode}", "info")
                self.interface.log(f"Symbol: {self.config.symbol}", "info")
                self.interface.log(f"Balance: ${display_balance:.2f}", "info")

            return True

        except Exception as e:
            if self.interface:
                self.interface.log(f"Initialization error: {e}", "error")
            return False

    def start(self):
        """Start trading loop"""
        if not self.initialize():
            return False

        self._stopped = False
        self.running = True
        self.paused = False

        # Start trading thread
        self.thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.thread.start()

        if self.interface:
            self.interface.log("Trading started!", "info")

        return True

    def _trading_loop(self):
        """Main trading loop"""
        while self.running:
            if not self.paused:
                self._update()
            time.sleep(0.5)  # Update every 500ms

    def _update(self):
        """Single trading update"""
        try:
            if not self.exchange or not self.strategy:
                return

            # Check circuit breaker
            if not self.circuit_breaker.can_execute():
                if self.interface:
                    self.interface.log(
                        f"Circuit breaker OPEN (failures: {self.circuit_breaker.stats.failures})",
                        "warn",
                    )
                return

            # Update price
            try:
                self.exchange.update_price()
                self.circuit_breaker.record_success()
            except Exception as e:
                self.circuit_breaker.record_failure()
                if self.interface:
                    self.interface.log(f"Price update failed: {e}", "error")
                return

            # Handle different exchange types
            if isinstance(self.exchange, OstiumExchange):
                self.metrics.price = self.exchange.get_current_price()
            else:
                self.metrics.price = self.exchange.get_price()

            # Get positions
            self.metrics.positions = self.exchange.get_positions()

            # Get signal from strategy
            bid = self.metrics.price - 0.02
            ask = self.metrics.price + 0.02
            signal = self.strategy.on_tick(
                self.metrics.price, bid, ask, self.metrics.positions
            )

            # Execute signal
            if signal and signal.get("action") == "open":
                side_val = signal["side"]
                side = side_val.value if hasattr(side_val, "value") else side_val

                if isinstance(self.exchange, OstiumExchange):
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    pos_id = loop.run_until_complete(
                        self.exchange.open_position(
                            symbol=self.config.symbol,
                            side=side,
                            volume=signal["amount"],
                            sl=signal.get("sl"),
                            tp=signal.get("tp"),
                        )
                    )
                else:
                    pos_id = self.exchange.open_position(
                        symbol=self.config.symbol,
                        side=side,
                        volume=signal["amount"],
                        sl=signal.get("sl"),
                        tp=signal.get("tp"),
                    )

                if pos_id:
                    self.metrics.trades = len(self.exchange.trades)

                    sl = signal.get("sl", 0)
                    tp = signal.get("tp", 0)
                    sl_tp_info = f" SL:{sl:.2f} TP:{tp:.2f}" if sl or tp else ""

                    if self.interface:
                        self.interface.log(
                            f"📈 {side.upper()} {signal['amount']} @ {self.metrics.price:.2f}{sl_tp_info}",
                            "trade",
                        )

            # Update metrics from exchange
            stats = self.exchange.get_stats()
            self.metrics.balance = stats["balance"]
            self.metrics.equity = stats["equity"]
            self.metrics.pnl = stats.get("net_pnl", 0)
            self.metrics.trades = stats.get("total_trades", self.metrics.trades)

            # Update interface
            if self.interface:
                self.interface.update_metrics(self.metrics.to_dict())

        except Exception as e:
            if self.interface:
                self.interface.log(f"Update error: {e}", "error")

    async def _async_update(self):
        """Update using parallel async fetch for improved performance."""
        try:
            if not self.exchange or not self.strategy:
                return

            from trading_bot.exchange.async_wrapper import AsyncExchangeWrapper
            from trading_bot.exchange.base import Exchange

            sync_exchange = self.exchange
            if asyncio.iscoroutinefunction(getattr(sync_exchange, "get_price", None)):
                async_exchange = sync_exchange
            else:
                async_exchange = AsyncExchangeWrapper(sync_exchange)  # type: ignore

            price, positions = await asyncio.gather(
                async_exchange.get_price(self.config.symbol),
                async_exchange.get_positions(self.config.symbol),
            )

            self.metrics.price = price
            self.metrics.positions = positions or []

            bid = self.metrics.price - 0.02
            ask = self.metrics.price + 0.02
            signal = self.strategy.on_tick(
                self.metrics.price, bid, ask, self.metrics.positions or []
            )

            if signal and signal.get("action") == "open":
                side_val = signal["side"]
                side = side_val.value if hasattr(side_val, "value") else side_val

                pos_id = await async_exchange.open_position(
                    symbol=self.config.symbol,
                    side=side,
                    amount=signal["amount"],
                    sl=signal.get("sl"),
                    tp=signal.get("tp"),
                )

                if pos_id:
                    self.metrics.trades += 1
                    sl = signal.get("sl", 0)
                    tp = signal.get("tp", 0)
                    sl_tp_info = f" SL:{sl:.2f} TP:{tp:.2f}" if sl or tp else ""

                    if self.interface:
                        self.interface.log(
                            f"📈 {side.upper()} {signal['amount']} @ {self.metrics.price:.2f}{sl_tp_info}",
                            "trade",
                        )

            if hasattr(self.exchange, "get_stats"):
                stats = self.exchange.get_stats()
                self.metrics.balance = stats.get("balance", self.metrics.balance)
                self.metrics.equity = stats.get("equity", self.metrics.equity)
                self.metrics.pnl = stats.get("net_pnl", 0)

            if self.interface:
                self.interface.update_metrics(self.metrics.to_dict())

        except Exception as e:
            if self.interface:
                self.interface.log(f"Async update error: {e}", "error")

    def stop(self):
        """Stop trading"""
        if self._stopped:
            return
        self._stopped = True

        self.running = False
        self.paused = True

        if self.thread:
            self.thread.join(timeout=2)

        if self.exchange and hasattr(self.exchange, "close"):
            try:
                self.exchange.close()
            except Exception:
                pass

        # Show final stats
        if self.exchange and self.interface:
            stats = self.exchange.get_stats()
            self.interface.log("", "info")
            self.interface.log("=" * 30, "info")
            self.interface.log("📊 SESSION ENDED", "info")
            self.interface.log("=" * 30, "info")
            self.interface.log(f"Final Balance: ${stats['balance']:.2f}", "info")
            self.interface.log(
                f"Net P&L: ${stats.get('net_pnl', 0):+.4f}",
                "profit" if stats.get("net_pnl", 0) >= 0 else "loss",
            )
            self.interface.log(f"Total Trades: {stats.get('total_trades', 0)}", "info")
            self.interface.log(f"Win Rate: {stats.get('win_rate', 0):.1f}%", "info")

    def pause(self):
        """Pause trading"""
        self.paused = True
        if self.interface:
            self.interface.log("Trading paused", "warn")

    def resume(self):
        """Resume trading"""
        self.paused = False
        if self.interface:
            self.interface.log("Trading resumed", "info")

    def get_stats(self) -> Dict[str, Any]:
        """Get current trading statistics"""
        if self.exchange:
            return self.exchange.get_stats()
        return {}
