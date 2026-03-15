"""
TUI Config Page - Configuration panel for trading bot
Allows navigation, viewing, and editing of settings in TUI mode
Includes selection UI for Provider, Mode, and Symbol
"""

from typing import Optional, List, Any, Callable, Tuple
from dataclasses import dataclass

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align

from trading_bot.interface.base import BaseInterface, InterfaceConfig


PROVIDER_OPTIONS = [
    ("simulator", "🏦 Simulator", "Paper trading with simulated market"),
    ("exness", "📈 Exness", "Forex/CFDs via Web Trading API"),
    ("ccxt", "💱 CCXT", "Crypto exchanges (Binance, Bybit, OKX)"),
    ("ostium", "⛽ Ostium", "DEX on Arbitrum"),
]

MODE_OPTIONS = [
    ("paper", "📘 Paper", "Pure simulation (no account needed)"),
    ("frontest", "📗 Frontest", "Demo account with real broker data"),
    ("real", "📕 Real", "Real account - REAL MONEY!"),
]

SYMBOL_OPTIONS = [
    ("XAUUSDm", "Gold (Micro)", "XAUUSD micro lots"),
    ("XAUUSD", "Gold (Standard)", "XAUUSD standard lots"),
    ("BTCUSDT", "Bitcoin", "BTC/USDT"),
    ("ETHUSDT", "Ethereum", "ETH/USDT"),
]

STRATEGY_OPTIONS = [
    ("XAUHedgingStrategy", "Gold Hedging", "Session-aware gold hedging strategy"),
    ("GridStrategy", "Grid Trading", "Range-based grid trading with mean reversion"),
    ("TrendStrategy", "Trend Following", "EMA crossover trend following"),
    ("HFTStrategy", "HFT Scalping", "High-frequency scalping with order book analysis"),
    ("NFIStrategy", "NFI Trend", "NostalgiaForInfinity multi-mode trend following"),
    ("IBBreakoutStrategy", "IB Breakout", "Initial Balance breakout strategy"),
    ("MomentumGridStrategy", "Momentum Grid", "Momentum-based grid strategy"),
    ("SevenCandleStrategy", "7 Candle", "7 Candle Breakout strategy"),
]

# Fields that require restart when changed
RESTART_REQUIRED_FIELDS = {
    "mode",
    "provider",
    "symbol",
    "exchange",
    "account",
    "credentials",
    "strategy",
}


@dataclass
class ConfigField:
    """Represents a single configuration field"""

    name: str
    value: Any
    section: str
    editable: bool = True
    options: Optional[List[Tuple[str, str, str]]] = None  # (value, label, description)
    requires_restart: bool = False


class SelectionState:
    def __init__(self):
        self.active = False
        self.field: Optional[ConfigField] = None
        self.options: Optional[List[Tuple[str, str, str]]] = []
        self.selected_index: int = 0
        self.current_value: Any = None


class NumericEditState:
    """State for editing numeric fields (leverage, SL/TP)"""

    def __init__(self):
        self.active = False
        self.field: Optional[ConfigField] = None
        self.edit_buffer: str = ""  # For direct number entry
        self.current_value: float = 0.0
        self.error_message: Optional[str] = None  # Validation error

    def start_edit(self, field: ConfigField):
        """Start editing a numeric field"""
        self.active = True
        self.field = field
        self.edit_buffer = ""
        self.error_message = None

        # Convert current value to string
        if isinstance(field.value, (int, float)):
            self.current_value = float(field.value)
            self.edit_buffer = (
                str(int(field.value))
                if field.value == int(field.value)
                else str(field.value)
            )

    def stop_edit(self):
        """Stop editing"""
        self.active = False
        self.field = None
        self.edit_buffer = ""
        self.current_value = 0.0
        self.error_message = None

    def get_value(self) -> Optional[float]:
        """Get the current numeric value from buffer"""
        if not self.edit_buffer:
            return None
        try:
            return float(self.edit_buffer)
        except ValueError:
            return None

    def set_error(self, message: str):
        """Set validation error"""
        self.error_message = message

    def clear_error(self):
        """Clear validation error"""
        self.error_message = None


# Numeric field configurations with ranges and steps
NUMERIC_FIELDS = {
    "Leverage": {
        "min": 10,
        "max": 5000,
        "step": 10,
        "config_key": "leverage",
    },
    "Stop Loss (pips)": {
        "min": 0,
        "max": 10000,
        "step": 10,
        "config_key": "sl_pips",
    },
    "Take Profit (pips)": {
        "min": 0,
        "max": 10000,
        "step": 10,
        "config_key": "tp_pips",
    },
    "Lot Size": {
        "min": 0.001,
        "max": 100,
        "step": 0.01,
        "config_key": "lot",
    },
    "Balance": {
        "min": 1,
        "max": 10000000,
        "step": 100,
        "config_key": "balance",
    },
    "Risk %": {
        "min": 0.1,
        "max": 100,
        "step": 0.1,
        "config_key": "risk_percent",
    },
    "Max Daily Loss": {
        "min": 0,
        "max": 1000000,
        "step": 10,
        "config_key": "max_daily_loss",
    },
    "Max Drawdown %": {
        "min": 0,
        "max": 100,
        "step": 1,
        "config_key": "max_drawdown",
    },
    "Trail Start (pips)": {
        "min": 0,
        "max": 10000,
        "step": 10,
        "config_key": "trail_start",
    },
    "Trailing Stop (pips)": {
        "min": 0,
        "max": 10000,
        "step": 10,
        "config_key": "trailing_stop_pips",
    },
    "Break Even Offset": {
        "min": 0,
        "max": 10000,
        "step": 5,
        "config_key": "break_even_offset",
    },
    "Break Even (pips)": {
        "min": 0,
        "max": 10000,
        "step": 5,
        "config_key": "break_even_pips",
    },
}


# Boolean fields that can be toggled
TOGGLE_FIELDS = {
    "Trailing Stop",
    "Break Even",
    "Auto Lot",
    "Asia Session",
    "London Open",
    "London Peak",
    "NY Session",
}


class ConfigPage:
    """
    Configuration page for TUI interface.
    Provides navigation through settings sections without actual editing.
    """

    # Sections in order
    SECTIONS = ["Basic Settings", "Strategy", "Risk Management", "Advanced Settings"]

    def __init__(self, config: InterfaceConfig, console: Optional[Console] = None):
        self.config = config
        self.console = console or Console()

        # Build fields from config
        self.fields = self._build_fields()

        # Navigation state
        self.current_section = 0
        self.current_field_index = 0
        self.selected_field = None  # Field being "edited" (highlighted)

        # Selection state for provider/mode/symbol
        self.selection = SelectionState()

        # Numeric editing state for leverage/SL/TP
        self.numeric_edit = NumericEditState()

        # Restart required message
        self.show_restart_message = False

        # Hot-swap feedback message
        self.hot_swap_message: Optional[str] = None
        self.hot_swap_timer: int = 0

        # Callbacks
        self.on_exit_callback: Optional[Callable] = None
        self.on_field_select_callback: Optional[Callable[[ConfigField], None]] = None
        self.on_config_change_callback: Optional[Callable[[str, Any], None]] = None

    def _build_fields(self) -> List[ConfigField]:
        """Build configuration fields from InterfaceConfig"""

        provider_value = (
            self.config.provider[0]
            if isinstance(self.config.provider, list)
            else self.config.provider
        )

        basic_fields = [
            ConfigField(
                "Provider",
                provider_value,
                "Basic Settings",
                options=PROVIDER_OPTIONS,
                requires_restart=True,
            ),
            ConfigField(
                "Mode",
                self.config.mode,
                "Basic Settings",
                options=MODE_OPTIONS,
                requires_restart=True,
            ),
            ConfigField(
                "Symbol",
                self.config.symbol,
                "Basic Settings",
                options=SYMBOL_OPTIONS,
                requires_restart=True,
            ),
            ConfigField("Lot Size", self.config.lot, "Basic Settings"),
            ConfigField(
                "Leverage",
                self.config.leverage,
                "Basic Settings",
                requires_restart=False,
            ),
            ConfigField("Balance", self.config.balance, "Basic Settings"),
        ]

        # Strategy section
        strategy_fields = [
            ConfigField(
                "Strategy",
                self.config.strategy,
                "Strategy",
                options=STRATEGY_OPTIONS,
                requires_restart=True,
            ),
            ConfigField(
                "Stop Loss (pips)",
                self.config.sl_pips,
                "Strategy",
                requires_restart=False,
            ),
            ConfigField(
                "Take Profit (pips)",
                self.config.tp_pips,
                "Strategy",
                requires_restart=False,
            ),
        ]

        # Risk Management section
        risk_fields = [
            ConfigField("Auto Lot", self.config.use_auto_lot, "Risk Management"),
            ConfigField("Risk %", self.config.risk_percent, "Risk Management"),
            ConfigField(
                "Max Daily Loss", self.config.max_daily_loss, "Risk Management"
            ),
            ConfigField("Max Drawdown %", self.config.max_drawdown, "Risk Management"),
        ]

        # Session filters
        session_fields = [
            ConfigField(
                "Asia Session", self.config.use_asia_session, "Risk Management"
            ),
            ConfigField("London Open", self.config.use_london_open, "Risk Management"),
            ConfigField("London Peak", self.config.use_london_open, "Risk Management"),
            ConfigField("NY Session", self.config.use_ny_session, "Risk Management"),
        ]

        # Advanced Settings section
        advanced_fields = [
            ConfigField(
                "Trailing Stop", self.config.trailing_stop, "Advanced Settings"
            ),
            ConfigField(
                "Trailing Stop (pips)",
                self.config.trail_start,
                "Advanced Settings",
            ),
            ConfigField("Break Even", self.config.break_even, "Advanced Settings"),
            ConfigField(
                "Break Even (pips)",
                self.config.break_even_offset,
                "Advanced Settings",
            ),
        ]

        return (
            basic_fields
            + strategy_fields
            + risk_fields
            + session_fields
            + advanced_fields
        )

    def get_current_section_fields(self) -> List[ConfigField]:
        """Get fields for the current section"""
        section_name = self.SECTIONS[self.current_section]
        return [f for f in self.fields if f.section == section_name]

    def get_field_at_index(
        self, section_fields: List[ConfigField], index: int
    ) -> Optional[ConfigField]:
        """Get field at index in section"""
        if 0 <= index < len(section_fields):
            return section_fields[index]
        return None

    def navigate_next(self):
        """Navigate to next field"""
        section_fields = self.get_current_section_fields()

        if self.current_field_index < len(section_fields) - 1:
            self.current_field_index += 1
        elif self.current_section < len(self.SECTIONS) - 1:
            # Move to next section
            self.current_section += 1
            self.current_field_index = 0

    def navigate_prev(self):
        """Navigate to previous field"""
        if self.current_field_index > 0:
            self.current_field_index -= 1
        elif self.current_section > 0:
            # Move to previous section
            self.current_section -= 1
            # Set to last field of the previous section
            prev_section_fields = self.get_current_section_fields()
            self.current_field_index = len(prev_section_fields) - 1

    def select_field(self):
        section_fields = self.get_current_section_fields()
        field = self.get_field_at_index(section_fields, self.current_field_index)

        if field and field.editable:
            if field.options:
                self._activate_selection(field)
            elif field.name in NUMERIC_FIELDS:
                self._activate_numeric_edit(field)
            elif isinstance(field.value, bool):
                self.selected_field = field
                if self.on_field_select_callback:
                    self.on_field_select_callback(field)
            else:
                self.selected_field = field
                if self.on_field_select_callback:
                    self.on_field_select_callback(field)
            return

        if field:
            self.selected_field = field
            if self.on_field_select_callback:
                self.on_field_select_callback(field)

    def _activate_selection(self, field: ConfigField):
        self.selection.active = True
        self.selection.field = field
        self.selection.options = field.options
        self.selection.current_value = field.value

        current_idx = 0
        if field.options:
            for idx, (value, label, desc) in enumerate(field.options):
                if value == field.value:
                    current_idx = idx
                    break
        self.selection.selected_index = current_idx

    def _deactivate_selection(self):
        self.selection.active = False
        self.selection.field = None
        self.selection.options = []
        self.selection.selected_index = 0

    def _activate_numeric_edit(self, field: ConfigField):
        self.numeric_edit.start_edit(field)
        self.selected_field = field
        if self.on_field_select_callback:
            self.on_field_select_callback(field)

    def _deactivate_numeric_edit(self, save: bool = False):
        if save and self.numeric_edit.field:
            field = self.numeric_edit.field
            new_value = self.numeric_edit.get_value()
            if new_value is not None:
                field.value = new_value
                self._update_config_value(field.name, new_value)
                if self.on_config_change_callback:
                    self.on_config_change_callback(field.name, new_value)
        self.numeric_edit.stop_edit()
        self.selected_field = None

    def _validate_numeric_input(self, value: float) -> tuple:
        if not self.numeric_edit.field:
            return False, None
        field_name = self.numeric_edit.field.name
        if field_name not in NUMERIC_FIELDS:
            return False, None
        config = NUMERIC_FIELDS[field_name]
        if value < config["min"] or value > config["max"]:
            return False, f"Must be between {config['min']} and {config['max']}"
        return True, None

    def _increment_numeric_value(self):
        if not self.numeric_edit.active or not self.numeric_edit.field:
            return
        field_name = self.numeric_edit.field.name
        if field_name not in NUMERIC_FIELDS:
            return
        config = NUMERIC_FIELDS[field_name]
        step = config["step"]
        current = self.numeric_edit.get_value() or self.numeric_edit.current_value
        new_value = min(current + step, config["max"])
        self.numeric_edit.edit_buffer = (
            str(int(new_value)) if new_value == int(new_value) else str(new_value)
        )
        self.numeric_edit.current_value = new_value
        self.numeric_edit.clear_error()

    def _decrement_numeric_value(self):
        if not self.numeric_edit.active or not self.numeric_edit.field:
            return
        field_name = self.numeric_edit.field.name
        if field_name not in NUMERIC_FIELDS:
            return
        config = NUMERIC_FIELDS[field_name]
        step = config["step"]
        current = self.numeric_edit.get_value() or self.numeric_edit.current_value
        new_value = max(current - step, config["min"])
        self.numeric_edit.edit_buffer = (
            str(int(new_value)) if new_value == int(new_value) else str(new_value)
        )
        self.numeric_edit.current_value = new_value
        self.numeric_edit.clear_error()

    def _confirm_numeric_edit(self):
        if not self.numeric_edit.active or not self.numeric_edit.field:
            return
        field = self.numeric_edit.field
        new_value = self.numeric_edit.get_value()
        if new_value is None:
            self.numeric_edit.set_error("Invalid number")
            return
        valid, error = self._validate_numeric_input(new_value)
        if not valid:
            self.numeric_edit.set_error(error)
            return
        field.value = new_value
        self._update_config_value(field.name, new_value)
        if self.on_config_change_callback:
            self.on_config_change_callback(field.name, new_value)
        self._deactivate_numeric_edit(save=False)

    def _confirm_selection(self):
        if not self.selection.active or not self.selection.field:
            return

        field = self.selection.field
        if not self.selection.options:
            return

        selected_option = self.selection.options[self.selection.selected_index]
        new_value = selected_option[0]

        if new_value != field.value:
            field.value = new_value
            self._update_config_value(field.name, new_value)

            if field.requires_restart:
                self.show_restart_message = True

            if self.on_config_change_callback:
                self.on_config_change_callback(field.name, new_value)

        self._deactivate_selection()

    def _update_config_value(self, field_name: str, new_value: Any):
        field_map = {
            "Provider": "provider",
            "Mode": "mode",
            "Symbol": "symbol",
            "Lot Size": "lot",
            "Balance": "balance",
            "Leverage": "leverage",
            "Stop Loss (pips)": "sl_pips",
            "Take Profit (pips)": "tp_pips",
            "Trailing Stop": "trailing_stop",
            "Trailing Stop (pips)": "trail_start",
            "Trail Start (pips)": "trail_start",
            "Break Even": "break_even",
            "Break Even (pips)": "break_even_offset",
            "Break Even Offset": "break_even_offset",
            "Auto Lot": "use_auto_lot",
            "Risk %": "risk_percent",
            "Max Daily Loss": "max_daily_loss",
            "Max Drawdown %": "max_drawdown",
            "Asia Session": "use_asia_session",
            "London Open": "use_london_open",
            "London Peak": "use_london_open",
            "NY Session": "use_ny_session",
        }

        config_key = field_map.get(field_name, field_name.lower().replace(" ", "_"))

        if hasattr(self.config, config_key):
            if config_key == "provider":
                self.config.provider = [new_value]
            else:
                setattr(self.config, config_key, new_value)

    def selection_up(self):
        if self.selection.selected_index > 0:
            self.selection.selected_index -= 1

    def selection_down(self):
        opts = self.selection.options
        if opts and self.selection.selected_index < len(opts) - 1:
            self.selection.selected_index += 1

    def deselect_field(self):
        self._deactivate_selection()
        self._deactivate_numeric_edit(save=False)
        self.selected_field = None

    def _handle_numeric_key(self, key: str) -> bool:
        if key == "escape":
            self._deactivate_numeric_edit(save=False)
            return True
        elif key == "enter":
            self._confirm_numeric_edit()
            return True
        elif key == "arrow_up" or key == "up":
            self._increment_numeric_value()
            return True
        elif key == "arrow_down" or key == "down":
            self._decrement_numeric_value()
            return True
        elif key == "backspace":
            if self.numeric_edit.edit_buffer:
                self.numeric_edit.edit_buffer = self.numeric_edit.edit_buffer[:-1]
                self.numeric_edit.clear_error()
            return True
        elif key == "." or key == "-":
            if key == "." and "." not in self.numeric_edit.edit_buffer:
                self.numeric_edit.edit_buffer += "."
                self.numeric_edit.clear_error()
            elif key == "-" and not self.numeric_edit.edit_buffer:
                self.numeric_edit.edit_buffer += "-"
                self.numeric_edit.clear_error()
            return True
        elif key.isdigit():
            self.numeric_edit.edit_buffer += key
            self.numeric_edit.clear_error()
            return True
        return False

    def handle_key(self, key: str) -> bool:
        if self.selection.active:
            return self._handle_selection_key(key)

        if self.numeric_edit.active:
            return self._handle_numeric_key(key)

        if key == "escape":
            self.deselect_field()
            if self.on_exit_callback:
                self.on_exit_callback()
            return True
        elif key == "enter":
            if self.selected_field:
                if self.selected_field.name in NUMERIC_FIELDS:
                    self._activate_numeric_edit(self.selected_field)
                elif isinstance(self.selected_field.value, bool):
                    self._toggle_boolean_field(self.selected_field)
                else:
                    self.deselect_field()
            else:
                self.select_field()
            return True
        elif key == "arrow_up" or key == "up":
            self.navigate_prev()
            self.deselect_field()
            return True
        elif key == "arrow_down" or key == "down":
            self.navigate_next()
            self.deselect_field()
            return True
        elif key == "arrow_left" or key == "left":
            if self.current_section > 0:
                self.current_section -= 1
                section_fields = self.get_current_section_fields()
                self.current_field_index = min(
                    self.current_field_index, len(section_fields) - 1
                )
            self.deselect_field()
            return True
        elif key == "arrow_right" or key == "right":
            if self.current_section < len(self.SECTIONS) - 1:
                self.current_section += 1
                section_fields = self.get_current_section_fields()
                self.current_field_index = min(
                    self.current_field_index, len(section_fields) - 1
                )
            self.deselect_field()
            return True

        return False

    def _toggle_boolean_field(self, field: ConfigField):
        """Toggle a boolean field value"""
        if not isinstance(field.value, bool):
            return
        field.value = not field.value
        self._update_config_value(field.name, field.value)
        if self.on_config_change_callback:
            self.on_config_change_callback(field.name, field.value)
        self.show_hot_swap_message(
            f"{field.name} {'enabled' if field.value else 'disabled'}"
        )

    def show_hot_swap_message(self, message: str = "Applied"):
        """Show hot-swap feedback message"""
        self.hot_swap_message = message
        self.hot_swap_timer = 3

    def _handle_selection_key(self, key: str) -> bool:
        if key == "escape":
            self._deactivate_selection()
            return True
        elif key == "enter":
            self._confirm_selection()
            return True
        elif key == "arrow_up" or key == "up":
            self.selection_up()
            return True
        elif key == "arrow_down" or key == "down":
            self.selection_down()
            return True
        return False

    def render(self) -> Panel:
        title_text = Text("⚙️ Configuration", style="bold cyan")

        section_indicator = " | ".join(
            [
                f"{'[yellow]' if i == self.current_section else '[dim]'}{s}[/{'[yellow]' if i == self.current_section else '[dim]'}"
                for i, s in enumerate(self.SECTIONS)
            ]
        )

        current_section_name = self.SECTIONS[self.current_section]
        section_title = Text(f"▸ {current_section_name}", style="bold yellow")

        table = Table(show_edge=False, expand=True, box=box.SIMPLE)
        table.add_column("Field", style="cyan", width=25)
        table.add_column("Value", style="white")

        section_fields = self.get_current_section_fields()

        for idx, cfg_field in enumerate(section_fields):
            is_selected = idx == self.current_field_index
            is_editing = self.selected_field == cfg_field

            if is_editing:
                field_name = f"▶ {cfg_field.name} ◀"
                field_style = "bold yellow"
                value_style = "bold yellow"
            elif is_selected:
                field_name = f"▸ {cfg_field.name}"
                field_style = "bold cyan"
                value_style = "cyan"
            else:
                field_name = f"  {cfg_field.name}"
                field_style = "dim cyan"
                value_style = "white"

            if cfg_field.options:
                value_str = str(cfg_field.value) + " ▾"
            else:
                value_str = str(cfg_field.value)

            if isinstance(cfg_field.value, bool):
                value_str = "✓" if cfg_field.value else "✗"

            table.add_row(
                Text(field_name, style=field_style), Text(value_str, style=value_style)
            )

        from rich.console import Group

        if self.selection.active:
            selection_panel = self._render_selection_overlay()
            content = Group(
                Text(section_indicator + "\n"),
                section_title,
                Text(),
                table,
                Text(),
                selection_panel,
            )
        elif self.numeric_edit.active:
            numeric_panel = self._render_numeric_edit_overlay()
            content = Group(
                Text(section_indicator + "\n"),
                section_title,
                Text(),
                table,
                Text(),
                numeric_panel,
            )
        else:
            hints = Text()
            hints.append("[↑/↓] Navigate  ", style="dim")
            hints.append("[←/→] Sections  ", style="dim")
            hints.append("[Enter] Select  ", style="dim")
            hints.append("[Esc] Back", style="dim")

            content = Group(
                Text(section_indicator + "\n"),
                section_title,
                Text(),
                table,
                Text(),
                Align.center(hints),
            )

        if self.show_restart_message:
            restart_msg = Text(
                "\n⚠️  Restart required for changes to take effect", style="bold red"
            )
            content = Group(content, restart_msg)

        if self.hot_swap_message and self.hot_swap_timer > 0:
            hot_swap_msg = Text(
                f"\n✓ Applied (hot-swap): {self.hot_swap_message}", style="bold green"
            )
            content = Group(content, hot_swap_msg)
            self.hot_swap_timer -= 1
            if self.hot_swap_timer == 0:
                self.hot_swap_message = None

        return Panel(
            content,
            title=title_text,
            border_style="cyan",
            padding=(1, 2),
        )

    def _render_selection_overlay(self) -> Panel:
        if not self.selection.field or not self.selection.options:
            return Panel("No options")

        field = self.selection.field

        title = Text(f"Select {field.name}", style="bold yellow")

        options_table = Table(show_edge=False, expand=True, box=box.SIMPLE)
        options_table.add_column("Option", style="white", width=30)
        options_table.add_column("Description", style="dim")

        for idx, (value, label, desc) in enumerate(self.selection.options):
            is_selected = idx == self.selection.selected_index

            if is_selected:
                opt_style = "bold yellow"
                marker = "▶ "
            else:
                opt_style = "white"
                marker = "  "

            if value == field.value:
                label = label + " (current)"

            options_table.add_row(
                Text(marker + label, style=opt_style),
                Text(desc, style="dim"),
            )

        hints = Text()
        hints.append("[↑/↓] Navigate  ", style="dim")
        hints.append("[Enter] Confirm  ", style="dim")
        hints.append("[Esc] Cancel", style="dim")

        return Panel(
            Group(title, Text(), options_table, Text(), Align.center(hints)),
            title="Selection",
            border_style="yellow",
            padding=(1, 2),
        )

    def _render_numeric_edit_overlay(self) -> Panel:
        if not self.numeric_edit.active or not self.numeric_edit.field:
            return Panel("No field")

        field = self.numeric_edit.field
        field_config = NUMERIC_FIELDS.get(field.name, {})

        title = Text(f"Edit {field.name}", style="bold yellow")

        display_value = (
            self.numeric_edit.edit_buffer
            if self.numeric_edit.edit_buffer
            else str(field.value)
        )
        range_text = (
            f"Range: {field_config.get('min', '?')} - {field_config.get('max', '?')}"
        )
        step_text = f"Step: {field_config.get('step', '?')}"

        value_display = Text(f"  {display_value}  ", style="bold cyan")
        range_display = Text(f"  {range_text} | {step_text}", style="dim")

        error_display = Text()
        if self.numeric_edit.error_message:
            error_display = Text(
                f"  ⚠️  {self.numeric_edit.error_message}", style="bold red"
            )

        hints = Text()
        hints.append("[↑/↓] +/-Step  ", style="dim")
        hints.append("[0-9] Type    ", style="dim")
        hints.append("[Enter] Save  ", style="dim")
        hints.append("[Esc] Cancel", style="dim")

        return Panel(
            Group(
                title,
                Text(),
                value_display,
                range_display,
                error_display,
                Text(),
                Align.center(hints),
            ),
            title="Numeric Input",
            border_style="green",
            padding=(1, 2),
        )


class TUIConfigInterface(BaseInterface):
    """
    TUI Config Interface - Handles configuration display and navigation.
    This is a read-only view of configuration, actual editing comes in Tasks 5-8.
    """

    def __init__(self, config: Optional[InterfaceConfig] = None):
        super().__init__(config)
        self.console = Console()
        self.config_page = ConfigPage(self.config, self.console)
        self.active = False

        # Set up callbacks
        self.config_page.on_exit_callback = self._on_exit
        self.config_page.on_field_select_callback = self._on_field_select
        self.config_page.on_config_change_callback = self._on_config_change

    def _on_exit(self):
        self.active = False

    def _on_field_select(self, field: ConfigField):
        """Hook for field selection. Override in subclasses if needed."""
        pass

    def _on_config_change(self, field_name: str, new_value: Any):
        """Hook for config change. Override in subclasses if needed."""
        pass

    def run(self):
        """Run config interface."""
        self.active = True
        self._render()

    def _render(self):
        """Render the config page"""
        panel = self.config_page.render()
        self.console.print(panel)

    def handle_key(self, key: str) -> bool:
        """
        Handle keyboard input.
        Returns True if config page handled the key, False to pass to main TUI.
        """
        return self.config_page.handle_key(key)

    def stop(self):
        """Stop config interface"""
        self.active = False

    def log(self, message: str, level: str = "info"):
        """Log a message"""
        pass  # Config page doesn't log

    def update_metrics(self, metrics: dict):
        """Update displayed metrics"""
        pass  # Config page doesn't show metrics
