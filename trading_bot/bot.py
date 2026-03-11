"""
Main Trading Bot - Orchestrates all components
"""

import logging
import time
from typing import Optional, List

from trading_bot.core.models import Config, TradeMode, OrderSide
from trading_bot.exchange.base import Exchange
from trading_bot.exchange.ccxt import CCXTExchange
from trading_bot.exchange.simulator import SimulatorExchange
from trading_bot.strategy.base import Strategy
from trading_bot.risk.manager import RiskManager

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot"""

    def __init__(self, config: Config):
        self.config = config
        self.exchange: Optional[Exchange] = None
        self.strategy: Optional[Strategy] = None
        self.risk = RiskManager(config)
        self._running = False

    @property
    def restart_required(self) -> bool:
        """Check if bot requires restart for any config changes"""
        return False

    def has_open_positions(self) -> bool:
        """Check if there are open positions"""
        if not self.exchange:
            return False
        return len(self.exchange.positions) > 0

    def get_open_positions(self) -> list:
        """Get list of open positions"""
        if not self.exchange:
            return []
        return list(self.exchange.positions)

    def close_all_positions(self, force: bool = False) -> tuple:
        """
        Close all open positions gracefully.

        Args:
            force: If True, close without confirmation (for shutdown)

        Returns:
            (success: bool, closed_count: int, message: str)
        """
        if not self.exchange:
            return False, 0, "No exchange connected"

        positions = self.exchange.positions
        if not positions:
            return True, 0, "No open positions"

        closed_count = 0
        failed = []

        for pos in list(positions):
            try:
                trade = self.exchange.close_position(pos)
                if trade:
                    closed_count += 1
                    self.risk.update_pnl(trade.pnl)
                    logger.info(f"Closed position {pos.id}: PnL={trade.pnl:.2f}")
                else:
                    failed.append(pos.id)
            except Exception as e:
                logger.error(f"Failed to close position {pos.id}: {e}")
                failed.append(pos.id)

        if failed:
            return False, closed_count, f"Failed to close {len(failed)} positions"
        return True, closed_count, f"Closed {closed_count} positions"

    def graceful_shutdown(self, close_positions: bool = True) -> dict:
        """
        Perform graceful shutdown of the bot.

        Args:
            close_positions: Whether to close open positions before shutdown

        Returns:
            Dict with shutdown status
        """
        logger.info("Initiating graceful shutdown...")

        result = {"positions_closed": 0, "success": True, "message": ""}

        if close_positions and self.has_open_positions():
            success, closed, message = self.close_all_positions(force=True)
            result["positions_closed"] = closed
            result["success"] = success
            result["message"] = message
            logger.info(f"Shutdown: {message}")

        self._running = False
        logger.info("Graceful shutdown complete")
        return result

    def restart(self, new_config: Config = None, strategy_class: type = None) -> bool:
        """
        Restart the bot with new configuration.

        Args:
            new_config: New Config to use (if None, uses current config)
            strategy_class: New strategy class to use (if None, keeps current)

        Returns:
            True if restart successful
        """
        logger.info("Initiating bot restart...")

        self.graceful_shutdown(close_positions=True)

        if new_config:
            self.config = new_config
            self.risk = RiskManager(self.config)

        if strategy_class:
            self.setup(strategy_class)
        elif self.strategy:
            pass
        else:
            logger.warning("No strategy class provided for restart")
            return False

        self._running = True
        logger.info("Bot restart complete")
        return True

    def hot_swap_config(self, updates: dict) -> tuple:
        """
        Apply configuration updates to running bot (hot-swap).

        Args:
            updates: Dict of field names and new values to apply

        Returns:
            (success: bool, message: str, applied: list, failed: list)
        """
        from trading_bot.interface.base import InterfaceConfig

        applied = []
        failed = []

        field_mapping = {
            "lot": "lots",
            "sl_pips": "stop_loss",
            "tp_pips": "take_profit",
            "trailing_stop": "trailing",
            "trail_start": "trail_start",
            "break_even": "use_break_even",
            "break_even_offset": "break_even_offset",
            "use_auto_lot": "use_auto_lot",
            "risk_percent": "risk_percent",
            "max_daily_loss": "max_daily_loss",
            "max_drawdown": "max_drawdown",
            "use_asia_session": "use_asia_session",
            "use_london_open": "use_london_open",
            "use_ny_session": "use_ny_session",
        }

        for field_name, new_value in updates.items():
            core_field = field_mapping.get(field_name, field_name)

            if not hasattr(self.config, core_field):
                failed.append(f"{field_name}: unknown field")
                continue

            old_value = getattr(self.config, core_field)

            try:
                if field_name in (
                    "lot",
                    "sl_pips",
                    "tp_pips",
                    "trail_start",
                    "break_even_offset",
                    "risk_percent",
                    "max_daily_loss",
                    "max_drawdown",
                ):
                    new_value = float(new_value)
                elif field_name in ("leverage",):
                    new_value = int(new_value)
                elif field_name in (
                    "trailing_stop",
                    "break_even",
                    "use_auto_lot",
                    "use_asia_session",
                    "use_london_open",
                    "use_ny_session",
                ):
                    new_value = bool(new_value)

                setattr(self.config, core_field, new_value)
                applied.append(f"{field_name}: {old_value} -> {new_value}")

            except (ValueError, TypeError) as e:
                failed.append(f"{field_name}: invalid value - {e}")

        if self.strategy and applied:
            self.strategy.config = self.config
        if self.risk and applied:
            self.risk.config = self.config

        if failed:
            success = False
            message = f"Hot-swap partially failed: {len(failed)} error(s)"
        else:
            success = True
            message = f"Hot-swap applied successfully: {len(applied)} setting(s)"

        return success, message, applied, failed

    def setup(self, strategy_class: type):
        """Initialize components"""
        # Create exchange
        if self.config.mode == TradeMode.BACKTEST:
            self.exchange = SimulatorExchange(self.config)
        else:
            self.exchange = CCXTExchange(self.config)
            if not self.exchange.connect():
                raise ConnectionError("Failed to connect")

        # Create strategy
        self.strategy = strategy_class(self.config)

        logger.info(f"Bot ready: {self.config.mode.value} | {strategy_class.__name__}")

    def run(self):
        """Main loop"""
        if not self.exchange or not self.strategy:
            raise RuntimeError("Not setup")

        logger.info("=" * 50)
        logger.info("STARTING BOT")
        logger.info("=" * 50)

        if self.config.mode == TradeMode.BACKTEST:
            self._run_backtest()
        else:
            self._run_live()

    def _run_backtest(self):
        """Backtest loop"""
        if isinstance(self.exchange, SimulatorExchange):
            # Generate data if none loaded
            if not self.exchange.data:
                # Use XAU data for XAU strategy, else crypto
                if "XAU" in self.config.symbol.upper():
                    self.exchange.generate_xau_data(90)
                else:
                    self.exchange.generate_synthetic_data(90)

        while self.exchange.tick():
            self._process_tick()

        self._print_results()

    def _run_live(self):
        """Live trading loop"""
        while True:
            try:
                self._process_tick()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(5)

    def _process_tick(self):
        """Single tick processing"""
        bid, ask = self.exchange.get_price()
        price = (bid + ask) / 2

        balance = self.exchange.get_balance()
        positions = self.exchange.positions

        # Check risk
        can_trade, reason = self.risk.check(balance.equity)
        if not can_trade:
            logger.warning(f"Risk limit: {reason}")
            return

        # Get signal (pass timestamp for session-aware strategies)
        timestamp = None
        if isinstance(self.exchange, SimulatorExchange):
            timestamp = self.exchange._current_time
        action = self.strategy.on_tick(price, bid, ask, positions, timestamp)

        if action:
            self._execute(action)

    def _execute(self, action: dict):
        """Execute action from strategy"""
        action_type = action.get("action")

        if action_type == "open":
            self.exchange.create_order(
                action["side"],
                action["amount"],
                action.get("price", 0),
                action.get("sl", 0),
                action.get("tp", 0),
            )
        elif action_type == "close":
            for pos in self.exchange.positions:
                if pos.id == action["position_id"]:
                    trade = self.exchange.close_position(pos)
                    if trade:
                        self.risk.update_pnl(trade.pnl)

    def _print_results(self):
        """Print backtest results"""
        if not isinstance(self.exchange, SimulatorExchange):
            return

        trades = self.exchange.trades
        if not trades:
            logger.info("No trades executed")
            return

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in trades)
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        final = self.exchange.get_balance()

        print("\n" + "=" * 50)
        print("BACKTEST RESULTS")
        print("=" * 50)
        print(f"Initial: ${self.config.initial_balance:,.2f}")
        print(f"Final:   ${final.equity:,.2f}")
        print(
            f"Return:  {((final.equity / self.config.initial_balance) - 1) * 100:+.2f}%"
        )
        print(f"Trades:  {len(trades)}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Wins: {len(wins)}, Losses: {len(losses)}")
        if wins:
            print(f"Avg Win: ${sum(t.pnl for t in wins) / len(wins):.2f}")
        if losses:
            print(f"Avg Loss: ${sum(t.pnl for t in losses) / len(losses):.2f}")
        print("=" * 50)
