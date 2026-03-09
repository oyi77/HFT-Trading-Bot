"""
Command Line Interface for Trading Bot
Simple text-based interface with logging
"""

import sys
import time
import signal
from datetime import datetime
from typing import Optional

from trading_bot.interface.base import BaseInterface, InterfaceConfig


class CLIInterface(BaseInterface):
    """Simple command-line interface"""

    def __init__(self, config: Optional[InterfaceConfig] = None, verbose: bool = False):
        super().__init__(config)
        self.verbose = verbose
        self.verbose = True

    def log(self, message: str, level: str = "info"):
        """Print log message"""
        if not self.verbose:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "[INFO]",
            "warn": "[WARN]",
            "error": "[ERROR]",
            "trade": "[TRADE]",
            "profit": "[PROFIT]",
            "loss": "[LOSS]",
        }.get(level, "[INFO]")

        print(f"[{timestamp}] {prefix} {message}")
        sys.stdout.flush()

    def update_metrics(self, metrics: dict):
        """Print metrics (in CLI, just log them)"""
        if not self.verbose:
            return

        price = metrics.get("price", 0)
        balance = metrics.get("balance", 0)
        equity = metrics.get("equity", 0)
        pnl = metrics.get("pnl", 0)
        trades = metrics.get("trades", 0)
        positions = metrics.get("positions", [])

        # Format positions
        pos_str = ""
        if positions:
            pos_details = []
            for pos in positions:
                if hasattr(pos, "side"):
                    side = pos.side.upper()
                    vol = getattr(pos, "volume", 0)
                    entry = getattr(pos, "entry_price", 0)
                    pos_details.append(f"{side}:{vol:.2f}@{entry:.0f}")
            pos_str = f" | Positions: {len(positions)} ({', '.join(pos_details)})"

        status_line = f"Price: ${price:.2f} | Balance: ${balance:.2f} | Equity: ${equity:.2f} | P&L: ${pnl:+.4f} | Trades: {trades}{pos_str}"
        print(f"\r{status_line:<120}", end="")
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

        # Keep running until stopped
        try:
            while self.running:
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
