"""
Terminal User Interface for Trading Bot
Using Rich for beautiful, responsive terminal UI
"""

import sys
import os
import time
import signal
from datetime import datetime
from typing import Optional, List, Any

from rich.live import Live
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align
from rich.columns import Columns

from trading_bot.interface.base import BaseInterface, InterfaceConfig


class TUIInterface(BaseInterface):
    """Rich-based Terminal User Interface"""

    def __init__(self, config: Optional[InterfaceConfig] = None):
        super().__init__(config)
        self.console = Console()
        self.paused = False

        # Trading data
        self.exchange: Any = None
        self.strategy: Any = None

        # Display data
        self.price = 0.0
        self.balance = config.balance if config else 100.0
        self.equity = config.balance if config else 100.0
        self.pnl = 0.0
        self.trade_count = 0
        self.status = "Initializing..."
        self.logs: List[str] = []
        self.positions: List[Any] = []

    def log(self, message: str, level: str = "info"):
        """Add log entry"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color code based on level
        color = {
            "info": "white",
            "warn": "yellow",
            "error": "red",
            "trade": "cyan",
            "profit": "green",
            "loss": "red",
        }.get(level, "white")

        self.logs.append(f"[{timestamp}] [{color}]{message}[/{color}]")
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]

    def update_metrics(self, metrics: dict):
        """Update display metrics"""
        self.price = metrics.get("price", self.price)
        self.balance = metrics.get("balance", self.balance)
        self.equity = metrics.get("equity", self.equity)
        self.pnl = metrics.get("pnl", self.pnl)
        self.trade_count = metrics.get("trades", self.trade_count)
        self.positions = metrics.get("positions", self.positions)

    def generate_display(self):
        """Generate the dashboard display"""
        # Header
        header = Text()
        header.append("🤖 Trading Bot  ", style="bold cyan")
        header.append(
            f"Mode: {self.config.mode.upper()}  ",
            style="green" if self.config.mode == "paper" else "yellow",
        )
        header.append(f"Symbol: {self.config.symbol}  ", style="white")
        header.append(f"Strategy: {self.config.strategy}", style="white")

        # Metrics panel
        metrics = Table(show_edge=False, show_header=False, expand=True)
        metrics.add_column(justify="left", style="dim cyan")
        metrics.add_column(justify="right")

        balance_style = "green" if self.balance >= self.config.balance else "red"
        equity_style = "green" if self.equity >= self.config.balance else "red"
        pnl_style = "green" if self.pnl >= 0 else "red"
        status_style = {"Running": "green", "Paused": "yellow", "Stopped": "red"}.get(
            self.status, "white"
        )

        metrics.add_row("Price", Text(f"${self.price:.2f}", style="white"))
        metrics.add_row("Balance", Text(f"${self.balance:.2f}", style=balance_style))
        metrics.add_row("Equity", Text(f"${self.equity:.2f}", style=equity_style))
        metrics.add_row("P&L", Text(f"${self.pnl:+.2f}", style=pnl_style))
        metrics.add_row("Trades", Text(str(self.trade_count), style="white"))
        metrics.add_row("Status", Text(self.status, style=status_style))

        metrics_panel = Panel(
            metrics, title="📊 Metrics", border_style="blue", width=30
        )

        # Positions panel
        pos_table = Table(box=box.SIMPLE, expand=True, pad_edge=False)
        pos_table.add_column("ID", width=4)
        pos_table.add_column("Side", width=5)
        pos_table.add_column("Vol", width=6, justify="right")
        pos_table.add_column("Entry", width=9, justify="right")
        pos_table.add_column("SL", width=9, justify="right")
        pos_table.add_column("P&L", width=10, justify="right")

        for pos in self.positions:
            # Calculate P&L if method exists
            if hasattr(pos, "calculate_profit"):
                pnl = pos.calculate_profit(self.price)
            else:
                pnl = 0

            pnl_str = f"${pnl:+.2f}"
            pnl_style = "green" if pnl >= 0 else "red"

            side = pos.side.upper() if hasattr(pos, "side") else "N/A"
            volume = f"{pos.volume:.2f}" if hasattr(pos, "volume") else "N/A"
            entry = f"{pos.entry_price:.2f}" if hasattr(pos, "entry_price") else "N/A"
            sl = f"{pos.sl:.2f}" if hasattr(pos, "sl") and pos.sl else "-"

            pos_table.add_row(
                str(pos.id) if hasattr(pos, "id") else "-",
                side,
                volume,
                entry,
                sl,
                Text(pnl_str, style=pnl_style),
            )

        if not self.positions:
            pos_table.add_row(
                "-", "-", "-", "-", "-", Text("No positions", style="dim")
            )

        pos_panel = Panel(
            pos_table,
            title=f"📈 Positions ({len(self.positions)})",
            border_style="green",
        )

        # Top row
        top_row = Columns([metrics_panel, pos_panel])

        # Logs panel
        log_text = (
            "\n".join(self.logs[-20:])
            if self.logs
            else Text("No activity...", style="dim")
        )
        log_panel = Panel(
            log_text, title="📜 Trade Log", border_style="yellow", height=12
        )

        # Footer
        footer = Text()
        footer.append("[Q]", style="bold cyan")
        footer.append(" Quit  ", style="white")
        footer.append("[S]", style="bold cyan")
        footer.append(" Stop  ", style="white")
        footer.append("[P]", style="bold cyan")
        footer.append(" Pause  ", style="white")
        footer.append("[R]", style="bold cyan")
        footer.append(" Resume", style="white")

        footer_panel = Panel(Align.center(footer), border_style="cyan")

        return Group(
            Panel(header, border_style="cyan"), top_row, log_panel, footer_panel
        )

    def handle_key(self, key: str):
        """Handle keyboard input"""
        key = key.lower()
        if key == "q":
            self.log("👋 Quitting...", "info")
            self.stop()
        elif key == "s":
            self.stop_trading()
        elif key == "p":
            self.paused = True
            self.status = "Paused"
            self.log("⏸ Paused", "warn")
        elif key == "r":
            self.paused = False
            self.status = "Running"
            self.log("▶️ Resumed", "info")

    def stop_trading(self):
        """Stop trading and show final stats"""
        if self.status == "Stopped":
            return
        self.status = "Stopped"
        self.paused = True
        self.log("⏹ Trading stopped", "warn")

        if self.on_stop_callback:
            self.on_stop_callback()

    def _setup_terminal(self):
        """Setup terminal for single character input"""
        try:
            import tty
            import termios
            import fcntl

            fd = sys.stdin.fileno()
            old_term = termios.tcgetattr(fd)
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)

            # Set non-blocking raw mode
            tty.setcbreak(fd)
            fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

            return fd, old_term, old_flags
        except Exception:
            return None, None, None

    def _restore_terminal(self, fd, old_term, old_flags):
        """Restore terminal settings"""
        try:
            import termios
            import fcntl

            if fd and old_term:
                termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
            if fd and old_flags is not None:
                fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)
        except Exception:
            pass

    def _read_key(self):
        """Read a single key if available"""
        try:
            return sys.stdin.read(1)
        except Exception:
            return None

    def run(self):
        """Run TUI interface"""
        # Clear screen and show welcome
        self.console.clear()
        self.console.print("""
[bold cyan]┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓[/bold cyan]
[bold cyan]┃                                                                  ┃[/bold cyan]
[bold cyan]┃   🤖  TRADING BOT SYSTEM                                         ┃[/bold cyan]
[bold cyan]┃                                                                  ┃[/bold cyan]
[bold cyan]┃   Multi-Asset | Multi-Provider | Paper Trading                   ┃[/bold cyan]
[bold cyan]┃                                                                  ┃[/bold cyan]
[bold cyan]┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛[/bold cyan]
        """)

        self.console.print(f"[green]Mode:[/green] {self.config.mode.upper()}")
        self.console.print(f"[green]Symbol:[/green] {self.config.symbol}")
        self.console.print(f"[green]Balance:[/green] ${self.config.balance:.2f}")
        self.console.print("\n[yellow]Press Enter to start...[/yellow]")

        try:
            input()
        except KeyboardInterrupt:
            return
        except EOFError:
            self.log("Non-interactive stdin detected, auto-starting.", "info")
            pass

        # Setup terminal
        fd, old_term, old_flags = self._setup_terminal()

        # Setup signal handler
        def signal_handler(sig, frame):
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start
        self.running = True
        self.status = "Running"

        # Call start callback
        if self.on_start_callback:
            self.on_start_callback(self.config)

        try:
            # Try Rich Live display first
            try:
                with Live(
                    self.generate_display(), refresh_per_second=4, screen=True
                ) as live:
                    while self.running:
                        # Check for keypress
                        key = self._read_key()
                        if key:
                            self.handle_key(key)

                        # Update display
                        try:
                            live.update(self.generate_display())
                        except BlockingIOError:
                            # Fallback to simple print if Live fails
                            break
                        time.sleep(0.05)
            except BlockingIOError:
                # Fallback: simple print loop without Rich Live
                self.console.print("[yellow]Falling back to simple display...[/yellow]")
                while self.running:
                    key = self._read_key()
                    if key:
                        self.handle_key(key)
                    self.console.clear()
                    self.console.print(self.generate_display())
                    time.sleep(0.5)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
        finally:
            self.stop()
            self._restore_terminal(fd, old_term, old_flags)
            self.console.print("\n[green]Goodbye![/green]")

    def stop(self):
        """Stop TUI interface"""
        if not self.running and self.paused:
            return
        self.running = False
        self.paused = True
        if self.on_stop_callback:
            self.on_stop_callback()
