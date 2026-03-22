"""
Trading Engine - Core trading logic that works with any interface
"""

import time
import threading
import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)
from dataclasses import dataclass

from trading_bot.exchange.simulator import SimulatorExchange
from trading_bot.exchange.ostium import OstiumExchange, create_ostium_exchange
from trading_bot.exchange.exness_exchange import ExnessExchange, create_exness_exchange
from trading_bot.exchange.bybit_exchange import BybitExchange, create_bybit_exchange
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.grid import GridStrategy, GridConfig
from trading_bot.strategy.trend import TrendStrategy, TrendConfig
from trading_bot.strategy.hft import HFTStrategy, HFTConfig
from trading_bot.strategy.scalping import ScalpingStrategy, ScalpingConfig
from trading_bot.strategy.nfi import NFIStrategy, NFIConfig
from trading_bot.strategy.ib_breakout import IBBreakoutStrategy, IBBreakoutConfig
from trading_bot.strategy.momentum import MomentumGridStrategy, MomentumGridConfig
from trading_bot.strategy.seven_candle import SevenCandleStrategy, SevenCandleConfig
from trading_bot.strategy.bb_macd_rsi import BBMacdRsiStrategy, BBMacdRsiConfig
from trading_bot.strategy.ai_strategy import (
    AIStrategy,
    AIStrategyConfig,
    BEST_XAU_H1,
    CONSERVATIVE_XAU_H1,
)
from trading_bot.strategy.zerolag import ZeroLagStrategy, ZeroLagConfig
from trading_bot.interface.base import InterfaceConfig
from trading_bot.risk.circuit_breaker import CircuitBreaker, CircuitBreakerError
from trading_bot.interface.telegram_notifier import TelegramNotifier
from trading_bot.risk.manager import RiskManager

# Type alias for exchanges
ExchangeType = Union[SimulatorExchange, OstiumExchange, ExnessExchange, BybitExchange]

# Strategy name -> (StrategyClass, ConfigClass) mapping
# Used by TradingEngine to instantiate the correct strategy from config.strategy string
STRATEGY_MAP = {
    "xau_hedging": (XAUHedgingStrategy, XAUHedgingConfig),
    "grid": (GridStrategy, GridConfig),
    "trend": (TrendStrategy, TrendConfig),
    "hft": (HFTStrategy, HFTConfig),
    "scalping": (ScalpingStrategy, ScalpingConfig),
    "nfi": (NFIStrategy, NFIConfig),
    "ib_breakout": (IBBreakoutStrategy, IBBreakoutConfig),
    "momentum": (MomentumGridStrategy, MomentumGridConfig),
    "seven_candle": (SevenCandleStrategy, SevenCandleConfig),
    "bb_macd_rsi": (BBMacdRsiStrategy, BBMacdRsiConfig),
    "ai": (AIStrategy, AIStrategyConfig),
    "zerolag": (ZeroLagStrategy, ZeroLagConfig),
}

# Named presets — use strategy="ai_best" or strategy="ai_conservative"
STRATEGY_PRESETS = {
    "ai_best": (AIStrategy, BEST_XAU_H1),
    "ai_conservative": (AIStrategy, CONSERVATIVE_XAU_H1),
}


@dataclass
class TradingMetrics:
    """Current trading metrics"""

    price: float = 0.0
    balance: float = 0.0
    equity: float = 0.0
    pnl: float = 0.0  # Realized PNL
    unrealized_pnl: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    trades: int = 0
    trade_history: Optional[List] = None
    positions: Optional[List] = None
    orders: Optional[List] = None

    def __post_init__(self):
        if self.positions is None:
            self.positions = []
        if self.trade_history is None:
            self.trade_history = []
        if self.orders is None:
            self.orders = []

    def to_dict(self) -> dict:
        import dataclasses

        def serialize(obj):
            if dataclasses.is_dataclass(obj):
                d = dataclasses.asdict(obj)
                # Ensure provider and ID prefixing (standard for all UI components)
                provider = getattr(obj, "provider", d.get("provider", "UNK"))
                prefix = f"{provider[:3].upper()}-"

                if "id" in d and not str(d["id"]).startswith(prefix):
                    d["id"] = f"{prefix}{d['id']}"
                if "unrealized_pnl" not in d and hasattr(obj, "unrealized_pnl"):
                    d["unrealized_pnl"] = obj.unrealized_pnl
                return d
            elif isinstance(obj, dict):
                d = dict(obj)
                prefix = f"{d.get('provider', 'UNK')[:3].upper()}-"
                if "id" in d and not str(d["id"]).startswith(prefix):
                    d["id"] = f"{prefix}{d['id']}"
                return d
            return str(obj)

        return {
            "price": self.price,
            "balance": self.balance,
            "equity": self.equity,
            "pnl": self.pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "trades": self.trades,
            "positions": [serialize(p) for p in self.positions],
            "orders": [serialize(o) for o in self.orders],
            "trade_history": [serialize(t) for t in self.trade_history],
        }


class TradingEngine:
    """
    Trading Engine - handles all trading logic
    Works with any interface (CLI, TUI, Web)
    """

    def __init__(self, config: InterfaceConfig, interface=None):
        self.config = config
        self.interface = interface
        # Wire engine back-reference so interface can access exchanges
        if interface is not None:
            interface._engine = self

        self.running = False
        self.paused = False
        self._stopped = False
        self.thread: Optional[threading.Thread] = None

        # Trading components
        self.exchanges: List[ExchangeType] = []
        self.strategy: Optional[XAUHedgingStrategy] = None

        # Risk Management
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60.0, name="exchange_api"
        )
        self.risk_manager = RiskManager(self.config)
        self.last_realized_pnl = 0.0

        # Telegram Notifications
        self.notifier = TelegramNotifier()

        # Metrics
        self.metrics = TradingMetrics()

    async def _initialize_async(self) -> bool:
        """Initialize trading components asynchronously"""
        try:
            # Create exchanges based on provider list and mode
            valid_providers = set()
            for provider_str in self.config.provider:
                provider_str = provider_str.lower()

                # If paper mode, spawn a simulator with this name
                if self.config.mode == "paper":
                    sim = SimulatorExchange(
                        initial_balance=self.config.balance, symbol=self.config.symbol
                    )
                    sim.name = provider_str.capitalize()
                    self.exchanges.append(sim)
                    valid_providers.add(provider_str)
                    if self.interface:
                        self.interface.log(
                            f"Started simulated paper exchange for {sim.name}", "info"
                        )
                    continue

                if provider_str == "ostium" and self.config.mode in (
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
                        continue

                    ostium = await create_ostium_exchange(
                        private_key,
                        rpc_url,
                        chain_id,
                        leverage=min(self.config.leverage, 50),
                    )

                    if not ostium:
                        if self.interface:
                            self.interface.log("Failed to connect to Ostium", "error")
                        continue

                    self.exchanges.append(ostium)
                    valid_providers.add("ostium")

                    if self.interface:
                        self.interface.log("Connected to Ostium DEX", "info")

                elif provider_str == "exness" and self.config.mode == "frontest":
                    account_id = os.getenv("EXNESS_ACCOUNT_ID")
                    token = os.getenv("EXNESS_TOKEN")
                    server = os.getenv("EXNESS_SERVER", "trial6")

                    if not account_id or not token:
                        if self.interface:
                            self.interface.log(
                                "EXNESS_ACCOUNT_ID and EXNESS_TOKEN required for frontest",
                                "error",
                            )
                        continue

                    exness = create_exness_exchange(
                        account_id=int(account_id), token=token, server=server
                    )

                    if not exness:
                        if self.interface:
                            self.interface.log(
                                "Failed to connect to Exness demo", "error"
                            )
                        continue

                    self.exchanges.append(exness)
                    valid_providers.add("exness")

                    if self.interface:
                        self.interface.log(
                            f"Connected to Exness Demo: {server}", "info"
                        )

                elif provider_str == "bybit" and self.config.mode == "frontest":
                    api_key = os.getenv("BYBIT_API_KEY")
                    api_secret = os.getenv("BYBIT_API_SECRET")

                    if not api_key or not api_secret:
                        if self.interface:
                            self.interface.log(
                                "BYBIT_API_KEY and BYBIT_API_SECRET required for frontest",
                                "error",
                            )
                        continue

                    bybit = create_bybit_exchange(
                        api_key,
                        api_secret,
                        testnet=True,
                        leverage=self.config.leverage,
                    )

                    if not bybit:
                        if self.interface:
                            self.interface.log(
                                f"Failed to connect to Bybit testnet", "error"
                            )
                        continue

                    self.exchanges.append(bybit)
                    valid_providers.add("bybit")

                    if self.interface:
                        self.interface.log("Connected to Bybit Testnet", "info")

            # Fallback to simulated paper trading if no live connections were made successfully, or if requested explicitly.
            if not self.exchanges or "simulator" in self.config.provider:
                if not any(isinstance(e, SimulatorExchange) for e in self.exchanges):
                    sim = SimulatorExchange(
                        initial_balance=self.config.balance, symbol=self.config.symbol
                    )
                    sim.name = "Simulator"
                    self.exchanges.append(sim)
                    valid_providers.add("simulator")

            # Create strategy based on config.strategy name
            strategy_name = getattr(self.config, "strategy", "xau_hedging")

            # Check presets first (ai_best, ai_conservative)
            if strategy_name in STRATEGY_PRESETS:
                StrategyClass, preset_config = STRATEGY_PRESETS[strategy_name]
                self.strategy = StrategyClass(preset_config)
                if self.interface:
                    self.interface.log(f"Using preset: {strategy_name}", "info")
            elif strategy_name in STRATEGY_MAP:
                StrategyClass, ConfigClass = STRATEGY_MAP[strategy_name]
                strategy_config = ConfigClass(lots=self.config.lot)
                # Forward SL/TP for configs that support them
                if hasattr(strategy_config, "stop_loss"):
                    strategy_config.stop_loss = int(self.config.sl_pips)
                if hasattr(strategy_config, "take_profit"):
                    strategy_config.take_profit = int(self.config.tp_pips)
                if hasattr(strategy_config, "sl_pips"):
                    strategy_config.sl_pips = float(self.config.sl_pips)
                if hasattr(strategy_config, "tp_pips"):
                    strategy_config.tp_pips = float(self.config.tp_pips)
                self.strategy = StrategyClass(strategy_config)
                if self.interface:
                    self.interface.log(f"Using strategy: {strategy_name}", "info")
            else:
                # Fallback to XAU Hedging
                strategy_config = XAUHedgingConfig(
                    lots=self.config.lot,
                    stop_loss=int(self.config.sl_pips),
                    take_profit=int(self.config.tp_pips),
                )
                self.strategy = XAUHedgingStrategy(strategy_config)
                strategy_name = "xau_hedging"
                if self.interface:
                    self.interface.log("Strategy not found, using xau_hedging", "warn")

            total_balance = sum(
                getattr(exchange, "balance", self.config.balance)
                for exchange in self.exchanges
            )
            total_equity = sum(
                getattr(exchange, "equity", self.config.balance)
                for exchange in self.exchanges
            )

            self.metrics.balance = total_balance
            self.metrics.equity = total_equity

            if self.interface:
                self.interface.log("Trading engine initialized", "info")
                self.interface.log(f"Mode: {self.config.mode}", "info")
                self.interface.log(f"Symbol: {self.config.symbol}", "info")
                self.interface.log(f"Balance: ${total_balance:.2f}", "info")
                self.interface.log(
                    f"Active Providers: {', '.join(valid_providers)}", "info"
                )

            return True

        except Exception as e:
            if self.interface:
                self.interface.log(f"Initialization error: {e}", "error")
            return False

    def start(self):
        """Start trading loop"""
        self._stopped = False
        self.running = True
        self.paused = False

        # Start trading thread
        self.thread = threading.Thread(target=self._thread_runner, daemon=True)
        self.thread.start()

        return True

    def _thread_runner(self):
        """Entry point for the background thread to run the asyncio event loop"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_trading_loop())
        except Exception as e:
            logger.error(f"Trading loop crashed: {e}")

    async def _async_trading_loop(self):
        """Main async trading loop inside the daemon thread"""
        success = await self._initialize_async()
        if not success:
            logger.error("Failed to initialize TradingEngine")
            self.running = False
            return

        if self.interface:
            self.interface.log("Trading started!", "info")

        while self.running:
            if not self.paused:
                await self._update()
            await asyncio.sleep(0.5)  # Update every 500ms

    async def _update(self):
        """Single asynchronous trading update"""
        try:
            if not self.exchanges or not self.strategy:
                return

            # Check circuit breaker
            if not self.circuit_breaker.can_execute():
                if self.interface:
                    self.interface.log(
                        f"Circuit breaker OPEN (failures: {self.circuit_breaker.stats.failures})",
                        "warn",
                    )
                return

            aggregated_positions = []
            aggregated_trade_history = []
            aggregated_orders = []
            aggregated_balance = 0.0
            aggregated_equity = 0.0
            aggregated_margin = 0.0
            aggregated_free_margin = 0.0
            aggregated_pnl = 0.0
            aggregated_trades = 0
            aggregated_unrealized_pnl = 0.0

            # Using the primary exchange to dictate the market price feed
            primary_exchange = self.exchanges[0]
            if hasattr(primary_exchange, "update_price"):
                if asyncio.iscoroutinefunction(primary_exchange.update_price):
                    await primary_exchange.update_price()
                else:
                    primary_exchange.update_price()
            global_market_price = (
                primary_exchange.get_price()
                if hasattr(primary_exchange, "get_price")
                else None
            )

            for exchange in self.exchanges:
                # Update price
                if exchange is not primary_exchange:
                    if hasattr(exchange, "update_price"):
                        if global_market_price is not None:
                            try:
                                if asyncio.iscoroutinefunction(exchange.update_price):
                                    await exchange.update_price(
                                        new_price=global_market_price
                                    )
                                else:
                                    exchange.update_price(new_price=global_market_price)
                                continue
                            except TypeError:
                                pass

                        if asyncio.iscoroutinefunction(exchange.update_price):
                            await exchange.update_price()
                        else:
                            exchange.update_price()

                broker_name = getattr(exchange, "name", exchange.__class__.__name__)
                if not isinstance(broker_name, str):
                    broker_name = str(exchange.__class__.__name__)

                # Get positions and inject provider
                positions = exchange.get_positions()
                for pos in positions:
                    if hasattr(pos, "provider"):
                        pos.provider = broker_name

                    # Compute unrealized logic if missing for simulators
                    if not hasattr(pos, "unrealized_pnl") or not getattr(
                        pos, "unrealized_pnl", 0
                    ):
                        if hasattr(pos, "calculate_profit") and hasattr(
                            exchange, "get_price"
                        ):
                            try:
                                # Safe pass if it fails to compute on dummy instances
                                pos.unrealized_pnl = pos.calculate_profit(
                                    getattr(exchange, "current_price", 0)
                                )
                            except Exception as e:
                                logger.debug(f"Failed to calculate profit: {e}")

                    aggregated_unrealized_pnl += (
                        getattr(pos, "unrealized_pnl", 0.0) or 0.0
                    )

                aggregated_positions.extend(positions)

                # Get pending orders and inject provider
                orders = []
                if hasattr(exchange, "get_orders"):
                    try:
                        orders_res = getattr(exchange, "get_orders")()
                        if hasattr(orders_res, "__iter__"):
                            orders = orders_res
                    except Exception as e:
                        val = getattr(exchange, "name", "Exchange")
                        logger.debug(f"Failed to get orders for {val}: {e}")

                try:
                    for order in orders:
                        if hasattr(order, "provider"):
                            order.provider = broker_name
                    aggregated_orders.extend(orders)
                except TypeError:
                    pass

                # Get trade history and inject provider
                historical_trades = getattr(exchange, "trades", [])
                for trade in historical_trades:
                    if isinstance(trade, dict):
                        if trade.get("action") == "open":
                            continue
                        trade_copy = dict(trade)
                        trade_copy["provider"] = broker_name
                        prefix = f"{broker_name[:3].upper()}-"
                        raw_id = trade_copy.get(
                            "id",
                            trade_copy.get(
                                "position_id",
                                trade_copy.get(
                                    "tradeID", trade_copy.get("orderId", "-")
                                ),
                            ),
                        )
                        if not str(raw_id).startswith(prefix):
                            trade_copy["id"] = f"{prefix}{raw_id}"
                        aggregated_trade_history.append(trade_copy)
                    else:
                        if hasattr(trade, "action") and trade.action == "open":
                            continue

                        if hasattr(trade, "provider"):
                            trade.provider = broker_name

                        # Standardize ID mapping natively for JS tracking
                        prefix = f"{broker_name[:3].upper()}-"
                        raw_id = getattr(
                            trade,
                            "id",
                            getattr(
                                trade,
                                "position_id",
                                getattr(
                                    trade, "tradeID", getattr(trade, "orderId", "-")
                                ),
                            ),
                        )
                        if not str(raw_id).startswith(prefix):
                            trade.id = f"{prefix}{raw_id}"

                        aggregated_trade_history.append(trade)

                # Fetch statistics
                stats = exchange.get_stats()
                aggregated_balance += stats.get(
                    "balance", getattr(exchange, "balance", self.config.balance)
                )
                aggregated_equity += stats.get(
                    "equity", getattr(exchange, "equity", self.config.balance)
                )
                margin = stats.get("margin_used", stats.get("margin", 0.0))
                aggregated_free_margin += stats.get(
                    "free_margin", stats.get("equity", self.config.balance) - margin
                )
                aggregated_pnl += stats.get("net_pnl", 0)
                aggregated_trades += stats.get(
                    "total_trades", len(getattr(exchange, "trades", []))
                )

            # Handle different exchange types for retrieving market price
            market_price = getattr(primary_exchange, "current_price", None)
            if market_price is None or not isinstance(market_price, (int, float)):
                if hasattr(primary_exchange, "get_price"):
                    try:
                        market_price = primary_exchange.get_price(self.config.symbol)
                    except TypeError:
                        market_price = primary_exchange.get_price()

            if not isinstance(market_price, (int, float)):
                market_price = 0.0

            self.metrics.price = market_price
            self.metrics.positions = aggregated_positions
            self.metrics.orders = aggregated_orders

            # Sort historical trades by time if available, otherwise just use them as-is. We cap at 500 to avoid huge payloads.
            self.metrics.trade_history = aggregated_trade_history[-500:]

            # Update Risk Manager with realized PNL delta
            pnl_delta = aggregated_pnl - self.last_realized_pnl
            if abs(pnl_delta) > 0.0001:
                self.risk_manager.update_pnl(pnl_delta)
                self.last_realized_pnl = aggregated_pnl

            # Check Risk Limits
            can_trade, risk_reason = self.risk_manager.check(aggregated_equity)
            if not can_trade:
                if self.interface:
                    self.interface.log(f"⚠️ TRADING HALTED: {risk_reason}", "error")
                # Notify Telegram about risk halt
                try:
                    self.notifier.notify_risk_alert(
                        alert_type="trading_halted",
                        message=risk_reason,
                        severity="high",
                    )
                except Exception:
                    pass
                # Skip signal processing
                self.metrics.balance = aggregated_balance
                self.metrics.equity = aggregated_equity
                self.metrics.margin = aggregated_margin
                self.metrics.free_margin = aggregated_free_margin
                self.metrics.pnl = aggregated_pnl
                self.metrics.unrealized_pnl = aggregated_unrealized_pnl
                self.metrics.trades = aggregated_trades
                if self.interface:
                    self.interface.update_metrics(self.metrics.to_dict())
                return

            # Get signal from strategy
            bid = self.metrics.price - 0.02
            ask = self.metrics.price + 0.02
            signal = self.strategy.on_tick(
                self.metrics.price, bid, ask, self.metrics.positions
            )

            # Execute signal concurrently on all active exchanges
            if signal and signal.get("action") == "open":
                # Risk check before execution
                if self.risk_manager:
                    can_trade, reason = self.risk_manager.check(self.metrics.equity)
                    if not can_trade:
                        if self.interface:
                            self.interface.log(f"Risk blocked: {reason}", "warn")
                        return

                side_val = signal["side"]
                side = side_val.value if hasattr(side_val, "value") else side_val

                for exchange in self.exchanges:
                    try:
                        if hasattr(
                            exchange, "open_position"
                        ) and asyncio.iscoroutinefunction(exchange.open_position):
                            pos_id = await exchange.open_position(
                                symbol=self.config.symbol,
                                side=side,
                                volume=signal["amount"],
                                sl=signal.get("sl"),
                                tp=signal.get("tp"),
                            )
                        else:
                            pos_id = exchange.open_position(
                                symbol=self.config.symbol,
                                side=side,
                                volume=signal["amount"],
                                sl=signal.get("sl"),
                                tp=signal.get("tp"),
                            )
                    except Exception as e:
                        broker_name = getattr(
                            exchange, "name", exchange.__class__.__name__
                        )
                        logger.error(f"Failed to open position on {broker_name}: {e}")
                        pos_id = None

                    if pos_id:
                        sl = signal.get("sl", 0)
                        tp = signal.get("tp", 0)
                        sl_tp_info = f" SL:{sl:.2f} TP:{tp:.2f}" if sl or tp else ""

                        broker_name = getattr(
                            exchange, "name", exchange.__class__.__name__
                        )
                        if self.interface:
                            self.interface.log(
                                f"📈 {side.upper()} {signal['amount']} @ {self.metrics.price:.2f} on {broker_name}{sl_tp_info}",
                                "trade",
                            )
                        # Telegram notification
                        try:
                            strategy_label = getattr(self.config, "strategy", "unknown")
                            self.notifier.notify_trade_open(
                                symbol=self.config.symbol,
                                side=side,
                                price=self.metrics.price,
                                sl=sl,
                                tp=tp,
                                lot_size=signal["amount"],
                                strategy_name=strategy_label,
                            )
                        except Exception:
                            pass

            # Update aggregated metrics
            self.metrics.balance = aggregated_balance
            self.metrics.equity = aggregated_equity
            self.metrics.margin = aggregated_margin
            self.metrics.free_margin = aggregated_free_margin
            self.metrics.pnl = aggregated_pnl
            self.metrics.unrealized_pnl = aggregated_unrealized_pnl
            self.metrics.trades = aggregated_trades

            # Update interface
            if self.interface:
                self.interface.update_metrics(self.metrics.to_dict())

        except Exception as e:
            if self.interface:
                self.interface.log(f"Update error: {e}", "error")

    def stop(self):
        """Stop trading"""
        if self._stopped:
            return
        self._stopped = True

        self.running = False
        self.paused = True

        if self.thread:
            self.thread.join(timeout=2)

        for exchange in self.exchanges:
            if hasattr(exchange, "close"):
                try:
                    exchange.close()
                except Exception as e:
                    logger.debug(f"Failed to close exchange: {e}")

        # Show final stats across all exchanges
        if self.exchanges and self.interface:
            self.interface.log("", "info")
            self.interface.log("=" * 30, "info")
            self.interface.log("📊 SESSION ENDED", "info")
            self.interface.log("=" * 30, "info")
            self.interface.log(
                f"Final Aggregated Balance: ${self.metrics.balance:.2f}", "info"
            )
            self.interface.log(
                f"Net Aggregated P&L: ${self.metrics.pnl:+.4f}",
                "profit" if self.metrics.pnl >= 0 else "loss",
            )
            self.interface.log(
                f"Total Aggregated Trades: {self.metrics.trades}", "info"
            )

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

    def _execute_close_safely(self, exchange: ExchangeType, pos_id: str):
        """Safely execute close operation across threads, handling async exchanges"""
        if hasattr(exchange, "close_position") and asyncio.iscoroutinefunction(
            exchange.close_position
        ):
            if hasattr(self, "_loop") and self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    exchange.close_position(pos_id), self._loop
                )
                return future.result(timeout=15)
            else:
                return asyncio.run(exchange.close_position(pos_id))
        else:
            return exchange.close_position(pos_id)

    def close_all_positions(self):
        """Close all open positions across all exchanges"""
        if not self.exchanges:
            return

        total_positions = 0
        for exchange in self.exchanges:
            positions = exchange.get_positions()
            total_positions += len(positions)

            for pos in positions:
                try:
                    self._execute_close_safely(exchange, pos.id)
                    # Telegram notification for closed position
                    try:
                        side_str = (
                            pos.side.value
                            if hasattr(pos.side, "value")
                            else str(pos.side)
                        )
                        pnl = getattr(pos, "unrealized_pnl", 0) or 0
                        self.notifier.notify_trade_close(
                            symbol=self.config.symbol,
                            side=side_str,
                            entry_price=pos.entry_price,
                            exit_price=self.metrics.price,
                            pnl=pnl,
                            reason="emergency_close",
                        )
                        self.risk_manager.on_trade_result(pnl)
                    except Exception:
                        pass
                except Exception as e:
                    broker_name = getattr(exchange, "name", exchange.__class__.__name__)
                    if self.interface:
                        self.interface.log(
                            f"Failed to close position {pos.id} on {broker_name}: {e}",
                            "error",
                        )

        if total_positions == 0:
            if self.interface:
                self.interface.log("No open positions to close", "info")
        else:
            if self.interface:
                self.interface.log(
                    f"Emergency: Closing {total_positions} positions across all brokers",
                    "warn",
                )
            try:
                self.notifier.notify_risk_alert(
                    alert_type="emergency_close",
                    message=f"Closed {total_positions} positions (emergency)",
                    severity="critical",
                )
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get current aggregated trading statistics"""
        return {
            "balance": getattr(self.metrics, "balance", 0),
            "equity": getattr(self.metrics, "equity", 0),
            "pnl": getattr(self.metrics, "pnl", 0),
            "unrealized_pnl": getattr(self.metrics, "unrealized_pnl", 0),
        }

    def close_position(self, pos_id: str, provider_name: str = None) -> bool:
        """Close a specific position by ID, optionally filtering by provider name"""
        if not self.exchanges:
            return False

        closed = False
        for exchange in self.exchanges:
            broker_name = getattr(exchange, "name", exchange.__class__.__name__)

            if provider_name and broker_name.lower() != provider_name.lower():
                continue

            # Parse un-prefixed ID for deep exchange logic
            prefix = f"{broker_name[:3].upper()}-"
            actual_pos_id = (
                pos_id[len(prefix) :] if pos_id.startswith(prefix) else pos_id
            )

            try:
                # See if position exists in this exchange before attempting
                positions = exchange.get_positions()
                if not any(
                    str(getattr(p, "id", p.get("id", "")))
                    in (str(pos_id), str(actual_pos_id))
                    for p in positions
                ):
                    continue

                try:
                    self._execute_close_safely(exchange, actual_pos_id)
                except Exception:
                    self._execute_close_safely(exchange, pos_id)
                closed = True
                if self.interface:
                    self.interface.log(
                        f"Closed position {pos_id} on {broker_name}", "warning"
                    )
            except Exception as e:
                if self.interface:
                    self.interface.log(
                        f"Failed to close position {pos_id} on {broker_name}: {e}",
                        "error",
                    )

        return closed

    def update_config(self, new_config: dict):
        """Update trading bot and strategy configuration dynamically"""
        if not new_config:
            return

        changes = []
        requires_restart = False

        # Check core fields that require a bot restart
        for core_key in ["symbol", "mode", "strategy", "timeframe"]:
            if core_key in new_config:
                val = new_config[core_key]
                if getattr(self.config, core_key) != val:
                    setattr(self.config, core_key, val)
                    changes.append(f"{core_key}={val}")
                    requires_restart = True

        if "provider" in new_config:
            val = new_config["provider"]
            if isinstance(val, str):
                val = [p.strip() for p in val.split(",")]
            if self.config.provider != val:
                self.config.provider = val
                changes.append(f"provider={val}")
                requires_restart = True

        if "lot" in new_config and float(new_config["lot"]) > 0:
            val = float(new_config["lot"])
            if self.config.lot != val:
                self.config.lot = val
                if self.strategy and hasattr(self.strategy, "config"):
                    self.strategy.config.lots = val
                changes.append(f"Lot={val}")

        if "sl_pips" in new_config and int(new_config["sl_pips"]) >= 0:
            val = int(new_config["sl_pips"])
            if self.config.sl_pips != val:
                self.config.sl_pips = val
                if self.strategy and hasattr(self.strategy, "config"):
                    self.strategy.config.stop_loss = val
                changes.append(f"SL={val}")

        if "tp_pips" in new_config and int(new_config["tp_pips"]) >= 0:
            val = int(new_config["tp_pips"])
            if self.config.tp_pips != val:
                self.config.tp_pips = val
                if self.strategy and hasattr(self.strategy, "config"):
                    self.strategy.config.take_profit = val
                changes.append(f"TP={val}")

        if "leverage" in new_config and int(new_config["leverage"]) > 0:
            val = int(new_config["leverage"])
            if self.config.leverage != val:
                self.config.leverage = val
                changes.append(f"Lev={val}x")

        # Advanced Settings
        for bool_key in [
            "trailing_stop",
            "break_even",
            "use_auto_lot",
            "use_asia_session",
            "use_london_open",
            "use_ny_session",
        ]:
            if bool_key in new_config:
                val = bool(new_config[bool_key])
                if getattr(self.config, bool_key) != val:
                    setattr(self.config, bool_key, val)
                    changes.append(f"{bool_key}={val}")

        for float_key in [
            "trail_start",
            "break_even_offset",
            "risk_percent",
            "max_daily_loss",
            "max_drawdown",
        ]:
            if float_key in new_config:
                val = float(new_config[float_key])
                if getattr(self.config, float_key) != val:
                    setattr(self.config, float_key, val)
                    changes.append(f"{float_key}={val}")

        if changes and self.interface:
            self.interface.log(f"Config Updated: {', '.join(changes)}", "warning")
            if requires_restart and hasattr(self.interface, "on_restart_callback"):
                self.interface.log(
                    f"Restarting engine due to core parameter change...", "warning"
                )
                threading.Timer(1.0, self.interface.on_restart_callback).start()
