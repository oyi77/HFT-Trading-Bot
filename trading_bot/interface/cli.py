"""
Command Line Interface for Trading Bot
Simple text-based interface with logging
"""

import sys
import time
import signal
import signal
import os
from datetime import datetime
from typing import Optional

from trading_bot.interface.base import BaseInterface, InterfaceConfig


class CLIInterface(BaseInterface):
    """Simple command-line interface"""

    def __init__(self, config: Optional[InterfaceConfig] = None, verbose: bool = False):
        super().__init__(config)
        self.verbose = verbose
        self.verbose = True
        self.logs = []
        self.metrics = {
            "price": 0.0,
            "balance": config.balance if config else 100.0,
            "equity": config.balance if config else 100.0,
            "pnl": 0.0,
            "margin": 0.0,
            "free_margin": config.balance if config else 100.0,
            "trades": 0,
            "positions": [],
        }
        self._needs_redraw = False
        self._last_redraw_time = 0

    def log(self, message: str, level: str = "info"):
        """Print log message"""
        if not self.verbose:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")

        colors = {
            "info": "\033[1;37m",
            "warn": "\033[1;33m",
            "error": "\033[1;31m",
            "trade": "\033[1;36m",
            "profit": "\033[1;32m",
            "loss": "\033[1;31m",
        }
        color = colors.get(level, "\033[1;37m")
        reset = "\033[0m"

        prefix = {
            "info": "[INFO]",
            "warn": "[WARN]",
            "error": "[ERROR]",
            "trade": "[TRADE]",
            "profit": "[PROFIT]",
            "loss": "[LOSS]",
        }.get(level, "[INFO]")

        self.logs.append(f"[{timestamp}] {color}{prefix} {message}{reset}")
        if len(self.logs) > 15:
            self.logs.pop(0)

        self._redraw()

    def show_restart_required_dialog(self, changed_fields: list) -> bool:
        """
        Show restart required dialog and get user confirmation.

        Args:
            changed_fields: List of field names that require restart

        Returns:
            True if user confirmed restart, False otherwise
        """
        print("\n" + "=" * 60)
        print("  ⚠️  RESTART REQUIRED  ⚠️")
        print("=" * 60)
        print("\nThe following settings require a restart to take effect:")
        print(f"\n  • {', '.join(changed_fields)}\n")
        print("Do you want to restart now? (y/n): ", end="")

        try:
            response = input().strip().lower()
            return response in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    def prompt_restart_with_confirmation(self, new_config) -> bool:
        """
        Prompt user for restart with confirmation and position safety check.

        Args:
            new_config: New configuration to apply after restart

        Returns:
            True if restart should proceed, False otherwise
        """
        if self.on_restart_required_callback:
            result = self.on_restart_required_callback(new_config.to_dict())
            if result is False:
                return False

        return True

    def update_metrics(self, metrics: dict):
        """Update metrics and schedule a redraw"""
        if not self.verbose:
            return

        self.metrics.update(metrics)

        # Debounce redraws slightly
        current_time = time.time()
        if current_time - self._last_redraw_time > 0.1:
            self._redraw()
        else:
            self._needs_redraw = True

    def _redraw(self):
        """Redraw the multi-line CLI dashboard"""
        self._last_redraw_time = time.time()
        self._needs_redraw = False

        # Clear screen and move cursor to top left
        os.system("cls" if os.name == "nt" else "clear")

        m = self.metrics
        pnl_color = "\033[1;32m" if m["pnl"] >= 0 else "\033[1;31m"
        reset = "\033[0m"

        print("=" * 80)
        mode = self.config.mode.upper() if self.config else "UNKNOWN"
        symbol = self.config.symbol if self.config else "UNKNOWN"
        print(f"\033[1;36m🤖 TRADING BOT CLI - Mode: {mode} | Symbol: {symbol}\033[0m")
        print("-" * 80)

        # Metrics line 1
        print(
            f" Price  : ${m.get('price', 0):>10.2f}    | Balance : ${m.get('balance', 0):>10.2f}  | Trades: {m.get('trades', 0)}"
        )

        unrealized = m.get("unrealized_pnl", m.get("equity", 0) - m.get("balance", 0))
        unrl_color = "\033[1;32m" if unrealized >= 0 else "\033[1;31m"

        print(
            f" Realized:{pnl_color}${m.get('pnl', 0):>+10.2f}{reset}    | Equity  : ${m.get('equity', 0):>10.2f}  | Unrel : {unrl_color}${unrealized:>+10.2f}{reset}"
        )

        # Metrics line 2
        print(
            f" Margin : ${m.get('margin', 0):>10.2f}    | Free Mgn: ${m.get('free_margin', 0):>10.2f}"
        )
        print("-" * 80)

        # Positions
        positions = m.get("positions", [])
        if not positions:
            print(" \033[1;30mNo active positions\033[0m")
        else:
            print(f" Active Positions ({len(positions)}):")
            for pos in positions:
                side = getattr(pos, "side", getattr(pos, "type", "UNKNOWN")).upper()
                side_color = "\033[1;32m" if side == "BUY" else "\033[1;31m"
                vol = getattr(pos, "volume", getattr(pos, "amount", 0))
                entry = getattr(pos, "entry_price", getattr(pos, "price", 0))
                print(
                    f"   {side_color}{side:<4}{reset} | Vol: {vol:<6.2f} | Entry: ${entry:.2f}"
                )

        print("-" * 80)
        print(" Recent Logs:")
        if not self.logs:
            print("   ...")
        else:
            for log_msg in self.logs:
                print(" " + log_msg)
        print("=" * 80)
        sys.stdout.flush()

    def run(self):
        """Run CLI interface"""
        self.running = True

        # Setup signal handler
        def signal_handler(sig, frame):
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Call start callback if set
        if self.on_start_callback:
            self.on_start_callback(self.config)

        # Initial draw
        self._redraw()

        # Keep running until stopped
        try:
            while self.running:
                if self._needs_redraw:
                    self._redraw()
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Stop CLI interface"""
        if not self.running:
            return

        self.running = False
        print("\n\n" + "=" * 60)
        print("📊 TRADING SESSION ENDED")
        print("=" * 60)

        if self.on_stop_callback:
            self.on_stop_callback()
