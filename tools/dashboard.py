"""
HFT Terminal UI — The "Polyrec" Style Dashboard.
A professional TUI for monitoring strategies, macro environment, and signals.
"""
import time
import sys
import os
from datetime import datetime
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich.align import Align
from rich.text import Text

# Import our macro module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_bot.core.macro_intelligence import MacroIntelligence

console = Console()

def make_layout() -> Layout:
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", size=15),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="market", ratio=1),
        Layout(name="stats", ratio=1),
    )
    return layout

class Header:
    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            Text("💎 BERKAHKARYA HFT BOT 💎", style="bold magenta"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return Panel(grid, style="white on blue")

def generate_market_table(macro_data) -> Table:
    table = Table(title="Macro Context (Bloomberg Replacement)", expand=True)
    table.add_column("Indicator", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_column("Change", justify="right")
    table.add_column("Signal", justify="center")
    
    dxy = macro_data.get("dxy", {})
    if "error" not in dxy:
        change_style = "bold red" if dxy.get("change", 0) > 0 else "bold green"
        table.add_row("US Dollar (DXY)", str(dxy.get("value")), f"[{change_style}]{dxy.get('change'):+.3f}[/]", dxy.get("signal"))
    
    us10y = macro_data.get("us10y", {})
    if "error" not in us10y:
        change_style = "bold red" if us10y.get("change", 0) > 0 else "bold green"
        table.add_row("US 10Y Yield", str(us10y.get("value")), f"[{change_style}]{us10y.get('change'):+.3f}[/]", us10y.get("signal"))
    
    table.add_row("Macro Sentiment", macro_data.get("sentiment"), "", "", style="bold yellow")
    return table

def generate_stats_table() -> Table:
    # Dummy data for now, ideally read from data/monitor_state.json
    table = Table(title="Strategy Performance (Health Check)", expand=True)
    table.add_column("Preset", style="cyan")
    table.add_column("Return", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Status", justify="center")
    
    table.add_row("mf_h1_best", "+89.3%", "3.71", "[bold green]OK[/]")
    table.add_row("mf_m15_ultra", "+16.3%", "2.57", "[bold green]OK[/]")
    table.add_row("ai_best", "-31.6%", "-2.83", "[bold red]WARN[/]")
    return table

def run_dashboard():
    macro = MacroIntelligence()
    layout = make_layout()
    layout["header"].update(Header())
    
    with Live(layout, refresh_per_second=1, screen=True):
        while True:
            macro_data = macro.get_summary()
            layout["market"].update(generate_market_table(macro_data))
            layout["stats"].update(generate_stats_table())
            layout["footer"].update(Panel(Align.center(Text("Press Ctrl+C to Exit", style="dim")), border_style="dim"))
            time.sleep(10) # Refresh macro every 10s

if __name__ == "__main__":
    run_dashboard()
