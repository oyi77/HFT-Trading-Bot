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
from trading_bot.core.agent_decision import TradingAgent

console = Console()

def make_layout() -> Layout:
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", size=20),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="market", ratio=1),
        Layout(name="agent", ratio=1),
    )
    return layout

class Header:
    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            Text("💎 BERKAHKARYA HFT BOT | OPEN-SOURCE ALPHA 💎", style="bold magenta"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return Panel(grid, style="white on blue")

def generate_agent_panel(agent_report) -> Panel:
    return Panel(
        Align.center(Text(agent_report, style="yellow")),
        title="🤖 AI Consultant (Goose Loop)",
        border_style="magenta"
    )

def generate_market_table(macro_data) -> Table:
    table = Table(title="Global Macro & Whale Flows (Kreo Clone)", expand=True)
    table.add_column("Indicator", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_column("Signal", justify="center")
    
    dxy = macro_data.get("dxy", {})
    if "error" not in dxy:
        table.add_row("US Dollar (DXY)", str(dxy.get("value")), dxy.get("signal"))
    
    us10y = macro_data.get("us10y", {})
    if "error" not in us10y:
        table.add_row("US 10Y Yield", str(us10y.get("value")), us10y.get("signal"))
    
    table.add_row("---", "---", "---")
    table.add_row("Whale Bias", "BULLISH", "ACCUMULATION", style="bold green")
    return table

def run_dashboard():
    macro = MacroIntelligence()
    agent = TradingAgent()
    layout = make_layout()
    layout["header"].update(Header())
    
    with Live(layout, refresh_per_second=1, screen=True):
        while True:
            macro_data = macro.get_summary()
            analysis = agent.analyze_situation(technical_signal="NEUTRAL")
            report = agent.generate_report(analysis)
            
            layout["market"].update(generate_market_table(macro_data))
            layout["agent"].update(generate_agent_panel(report))
            layout["footer"].update(Panel(Align.center(Text("Status: Monitor Active | Press Ctrl+C to Exit", style="dim")), border_style="dim"))
            time.sleep(5)


if __name__ == "__main__":
    run_dashboard()
