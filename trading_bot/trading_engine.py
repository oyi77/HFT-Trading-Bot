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

# Type alias for exchanges
ExchangeType = Union[SimulatorExchange, OstiumExchange, ExnessExchange, BybitExchange]


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
        
        serialized_positions = []
        for p in self.positions:
            if dataclasses.is_dataclass(p):
                d = dataclasses.asdict(p)
                if hasattr(p, "provider") and "provider" not in d:
                    d["provider"] = p.provider
                prefix = f"{d.get('provider', 'UNK')[:3].upper()}-"
                if "id" in d and not str(d["id"]).startswith(prefix):
                    d["id"] = f"{prefix}{d['id']}"
                if hasattr(p, "unrealized_pnl") and "unrealized_pnl" not in d:
                    d["unrealized_pnl"] = p.unrealized_pnl
                serialized_positions.append(d)
            elif hasattr(p, "to_dict"):
                d = p.to_dict()
                prefix = f"{getattr(p, 'provider', 'UNK')[:3].upper()}-"
                if "id" in d and not str(d["id"]).startswith(prefix):
                    d["id"] = f"{prefix}{d['id']}"
                serialized_positions.append(d)
            elif hasattr(p, "__dict__"):
                d = dict(p.__dict__)
                prefix = f"{getattr(p, 'provider', 'UNK')[:3].upper()}-"
                if "id" in d and not str(d["id"]).startswith(prefix):
                    d["id"] = f"{prefix}{d['id']}"
                serialized_positions.append(d)
            else:
                d = dict(p) if isinstance(p, dict) else p
                if isinstance(d, dict):
                    prefix = f"{d.get('provider', 'UNK')[:3].upper()}-"
                    if "id" in d and not str(d["id"]).startswith(prefix):
                        d["id"] = f"{prefix}{d['id']}"
                serialized_positions.append(d)
                
        serialized_orders = []
        for o in getattr(self, "orders", []):
            if dataclasses.is_dataclass(o):
                d = dataclasses.asdict(o)
                if hasattr(o, "provider") and "provider" not in d:
                    d["provider"] = o.provider
                serialized_orders.append(d)
            elif hasattr(o, "to_dict"):
                serialized_orders.append(o.to_dict())
            elif hasattr(o, "__dict__"):
                serialized_orders.append(o.__dict__)
            else:
                serialized_orders.append(o)
                
        return {
            "price": self.price,
            "balance": self.balance,
            "equity": self.equity,
            "pnl": self.pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "trades": self.trades,
            "positions": serialized_positions,
            "orders": serialized_orders,
            "trade_history": self.trade_history,
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
        self.exchanges: List[ExchangeType] = []
        self.strategy: Optional[XAUHedgingStrategy] = None

        # Metrics
        self.metrics = TradingMetrics()

    def initialize(self) -> bool:
        """Initialize trading components"""
        try:
            # Create exchanges based on provider list and mode
            valid_providers = set()
            for provider_str in self.config.provider:
                provider_str = provider_str.lower()
                
                # If paper mode, spawn a simulator with this name
                if self.config.mode == "paper":
                    sim = SimulatorExchange(initial_balance=self.config.balance, symbol=self.config.symbol)
                    sim.name = provider_str.capitalize()
                    self.exchanges.append(sim)
                    valid_providers.add(provider_str)
                    if self.interface:
                        self.interface.log(f"Started simulated paper exchange for {sim.name}", "info")
                    continue
                
                if provider_str == "ostium" and self.config.mode in ("frontest", "real"):
                    # Use real Ostium exchange
                    private_key = os.getenv("OSTIUM_PRIVATE_KEY")
                    rpc_url = os.getenv("OSTIUM_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc")
                    chain_id = int(os.getenv("OSTIUM_CHAIN_ID", "421614"))
    
                    if not private_key:
                        if self.interface:
                            self.interface.log("OSTIUM_PRIVATE_KEY not found", "error")
                        continue
    
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
                        continue
    
                    self.exchanges.append(ostium)
                    valid_providers.add("ostium")
    
                    if self.interface:
                        self.interface.log("Connected to Ostium DEX", "info")
    
                elif provider == "exness" and self.config.mode == "frontest":
                    account_id = os.getenv("EXNESS_ACCOUNT_ID")
                    token = os.getenv("EXNESS_TOKEN")
                    server = os.getenv("EXNESS_SERVER", "trial6")
    
                    if not account_id or not token:
                        if self.interface:
                            self.interface.log("EXNESS_ACCOUNT_ID and EXNESS_TOKEN required for frontest", "error")
                        continue
    
                    exness = create_exness_exchange(
                        account_id=int(account_id), token=token, server=server
                    )
    
                    if not exness:
                        if self.interface:
                            self.interface.log("Failed to connect to Exness demo", "error")
                        continue
    
                    self.exchanges.append(exness)
                    valid_providers.add("exness")
    
                    if self.interface:
                        self.interface.log(f"Connected to Exness Demo: {server}", "info")
    
                elif provider == "bybit" and self.config.mode == "frontest":
                    api_key = os.getenv("BYBIT_API_KEY")
                    api_secret = os.getenv("BYBIT_API_SECRET")
    
                    if not api_key or not api_secret:
                        if self.interface:
                            self.interface.log("BYBIT_API_KEY and BYBIT_API_SECRET required for frontest", "error")
                        continue
    
                    bybit = create_bybit_exchange(
                        api_key,
                        api_secret,
                        testnet=True,
                        leverage=self.config.leverage,
                    )
    
                    if not bybit:
                        if self.interface:
                            self.interface.log(f"Failed to connect to Bybit testnet", "error")
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

            # Create strategy
            strategy_config = XAUHedgingConfig(
                lots=self.config.lot,
                stop_loss=int(self.config.sl_pips),
                take_profit=int(self.config.tp_pips),
            )
            self.strategy = XAUHedgingStrategy(strategy_config)

            total_balance = sum(getattr(exchange, "balance", self.config.balance) for exchange in self.exchanges)
            total_equity = sum(getattr(exchange, "equity", self.config.balance) for exchange in self.exchanges)
            
            self.metrics.balance = total_balance
            self.metrics.equity = total_equity

            if self.interface:
                self.interface.log("Trading engine initialized", "info")
                self.interface.log(f"Mode: {self.config.mode}", "info")
                self.interface.log(f"Symbol: {self.config.symbol}", "info")
                self.interface.log(f"Balance: ${total_balance:.2f}", "info")
                self.interface.log(f"Active Providers: {', '.join(valid_providers)}", "info")

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
            if not self.exchanges or not self.strategy:
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
                primary_exchange.update_price()
            global_market_price = primary_exchange.get_price() if hasattr(primary_exchange, "get_price") else None

            for exchange in self.exchanges:
                # Update price
                if exchange is not primary_exchange:
                    if isinstance(exchange, SimulatorExchange) and global_market_price is not None:
                        exchange.update_price(new_price=global_market_price)
                    elif hasattr(exchange, "update_price"):
                        exchange.update_price()
    
                broker_name = getattr(exchange, "name", exchange.__class__.__name__)
                
                # Get positions and inject provider
                positions = exchange.get_positions()
                for pos in positions:
                    if isinstance(pos, dict):
                        pos["provider"] = broker_name
                    else:
                        try:
                            pos.provider = broker_name
                        except AttributeError:
                            # Fallback if slots or immutable, wrap it or use custom property
                            pass
                        
                    # Compute unrealized logic if missing for simulators 
                    if not isinstance(pos, dict) and not hasattr(pos, "unrealized_pnl"):
                        if hasattr(pos, "calculate_profit") and hasattr(exchange, "get_price"):
                            try:
                                pos.unrealized_pnl = pos.calculate_profit(exchange.get_price())
                            except Exception:
                                pass
                                
                    unrealized = pos.get("unrealized_pnl", 0.0) if isinstance(pos, dict) else getattr(pos, "unrealized_pnl", 0.0)
                    aggregated_unrealized_pnl += unrealized or 0.0
                        
                aggregated_positions.extend(positions)
                
                # Get pending orders and inject provider
                orders = []
                if hasattr(exchange, "get_orders"):
                    try:
                        orders = exchange.get_orders() or []
                    except Exception:
                        pass
                elif hasattr(exchange, "exchange") and hasattr(exchange.exchange, "fetch_open_orders"):
                    try:
                        orders = exchange.exchange.fetch_open_orders() or []
                    except Exception:
                        pass
                        
                for order in orders:
                    if isinstance(order, dict):
                        order["provider"] = broker_name
                    else:
                        try:
                            order.provider = broker_name
                        except AttributeError:
                            pass
                aggregated_orders.extend(orders)
                
                # Get trade history and inject provider
                historical_trades = getattr(exchange, "trades", [])
                for trade in historical_trades:
                    # Exclude 'open' action logs since history should reflect closures/results
                    if isinstance(trade, dict) and trade.get("action") == "open":
                        continue
                        
                    # We inject a copy so we don't dirty the exchange's internal structs if they are dictionaries
                    if isinstance(trade, dict):
                        trade_copy = dict(trade)
                        trade_copy["provider"] = broker_name
                        # Standardize ID mapping natively for JS tracking
                        prefix = f"{broker_name[:3].upper()}-"
                        raw_id = trade_copy.get("position_id", trade_copy.get("tradeID", trade_copy.get("orderId", "-")))
                        trade_copy["id"] = f"{prefix}{raw_id}" if not str(raw_id).startswith(prefix) else raw_id
                        aggregated_trade_history.append(trade_copy)
                    elif hasattr(trade, "__dict__"):
                        trade.provider = broker_name
                        prefix = f"{broker_name[:3].upper()}-"
                        raw_id = getattr(trade, "position_id", getattr(trade, "tradeID", getattr(trade, "orderId", "-")))
                        if not hasattr(trade, "id") or not str(getattr(trade, "id")).startswith(prefix):
                            trade.id = f"{prefix}{raw_id}" if not str(raw_id).startswith(prefix) else raw_id
                        aggregated_trade_history.append(trade)
                        
                # Fetch statistics
                stats = exchange.get_stats()
                aggregated_balance += stats.get("balance", getattr(exchange, "balance", self.config.balance))
                aggregated_equity += stats.get("equity", getattr(exchange, "equity", self.config.balance))
                margin = stats.get("margin_used", stats.get("margin", 0.0))
                aggregated_free_margin += stats.get("free_margin", stats.get("equity", self.config.balance) - margin)
                aggregated_pnl += stats.get("net_pnl", 0)
                aggregated_trades += stats.get("total_trades", len(getattr(exchange, "trades", [])))
                
            # Handle different exchange types for retrieving market price
            if isinstance(primary_exchange, OstiumExchange):
                self.metrics.price = primary_exchange.get_current_price()
            else:
                self.metrics.price = primary_exchange.get_price()

            self.metrics.positions = aggregated_positions
            self.metrics.orders = aggregated_orders
            
            # Sort historical trades by time if available, otherwise just use them as-is. We cap at 500 to avoid huge payloads.
            self.metrics.trade_history = aggregated_trade_history[-500:]

            # Get signal from strategy
            bid = self.metrics.price - 0.02
            ask = self.metrics.price + 0.02
            signal = self.strategy.on_tick(
                self.metrics.price, bid, ask, self.metrics.positions
            )

            # Execute signal concurrently on all active exchanges
            if signal and signal.get("action") == "open":
                side_val = signal["side"]
                side = side_val.value if hasattr(side_val, "value") else side_val

                for exchange in self.exchanges:
                    if isinstance(exchange, OstiumExchange):
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
    
                        pos_id = loop.run_until_complete(
                            exchange.open_position(
                                symbol=self.config.symbol,
                                side=side,
                                volume=signal["amount"],
                                sl=signal.get("sl"),
                                tp=signal.get("tp"),
                            )
                        )
                    else:
                        pos_id = exchange.open_position(
                            symbol=self.config.symbol,
                            side=side,
                            volume=signal["amount"],
                            sl=signal.get("sl"),
                            tp=signal.get("tp"),
                        )
    
                    if pos_id:
                        sl = signal.get("sl", 0)
                        tp = signal.get("tp", 0)
                        sl_tp_info = f" SL:{sl:.2f} TP:{tp:.2f}" if sl or tp else ""
    
                        broker_name = getattr(exchange, "name", exchange.__class__.__name__)
                        if self.interface:
                            self.interface.log(
                                f"📈 {side.upper()} {signal['amount']} @ {self.metrics.price:.2f} on {broker_name}{sl_tp_info}",
                                "trade",
                            )

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
                except Exception:
                    pass

        # Show final stats across all exchanges
        if self.exchanges and self.interface:
            self.interface.log("", "info")
            self.interface.log("=" * 30, "info")
            self.interface.log("📊 SESSION ENDED", "info")
            self.interface.log("=" * 30, "info")
            self.interface.log(f"Final Aggregated Balance: ${self.metrics.balance:.2f}", "info")
            self.interface.log(
                f"Net Aggregated P&L: ${self.metrics.pnl:+.4f}",
                "profit" if self.metrics.pnl >= 0 else "loss",
            )
            self.interface.log(f"Total Aggregated Trades: {self.metrics.trades}", "info")

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
                    if isinstance(exchange, OstiumExchange):
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        loop.run_until_complete(exchange.close_position(pos.id))
                    else:
                        exchange.close_position(pos.id)
                except Exception as e:
                    broker_name = getattr(exchange, "name", exchange.__class__.__name__)
                    if self.interface:
                        self.interface.log(f"Failed to close position {pos.id} on {broker_name}: {e}", "error")
        
        if total_positions == 0:
            if self.interface:
                self.interface.log("No open positions to close", "info")
        else:
            if self.interface:
                self.interface.log(f"Emergency: Closing {total_positions} positions across all brokers", "warn")

    def get_stats(self) -> Dict[str, Any]:
        """Get current aggregated trading statistics"""
        return {
            "balance": getattr(self.metrics, "balance", 0),
            "equity": getattr(self.metrics, "equity", 0),
            "pnl": getattr(self.metrics, "pnl", 0),
            "unrealized_pnl": getattr(self.metrics, "unrealized_pnl", 0)
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
            actual_pos_id = pos_id[len(prefix):] if pos_id.startswith(prefix) else pos_id
                
            try:
                # See if position exists in this exchange before attempting
                positions = exchange.get_positions()
                if not any(str(getattr(p, 'id', p.get('id', ''))) in (str(pos_id), str(actual_pos_id)) for p in positions):
                    continue
                    
                if isinstance(exchange, OstiumExchange):
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(exchange.close_position(actual_pos_id))
                else:
                    try:
                        exchange.close_position(actual_pos_id)
                    except Exception:
                        exchange.close_position(pos_id)
                closed = True
                if self.interface:
                    self.interface.log(f"Closed position {pos_id} on {broker_name}", "warning")
            except Exception as e:
                if self.interface:
                    self.interface.log(f"Failed to close position {pos_id} on {broker_name}: {e}", "error")
        
        
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
            "use_ny_session"
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
            "max_drawdown"
        ]:
            if float_key in new_config:
                val = float(new_config[float_key])
                if getattr(self.config, float_key) != val:
                    setattr(self.config, float_key, val)
                    changes.append(f"{float_key}={val}")
                
        if changes and self.interface:
            self.interface.log(f"Config Updated: {', '.join(changes)}", "warning")
            if requires_restart and hasattr(self.interface, 'on_restart_callback'):
                self.interface.log(f"Restarting engine due to core parameter change...", "warning")
                threading.Timer(1.0, self.interface.on_restart_callback).start()
