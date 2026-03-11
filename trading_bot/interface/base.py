"""
Base interface class for trading bot
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, List


class ValidationError(Exception):
    """Custom validation error"""

    pass


@dataclass
class InterfaceConfig:
    """Configuration for interfaces"""

    mode: str = "paper"
    provider: List[str] = field(default_factory=lambda: ["simulator"])
    account: str = "demo"  # demo or real
    symbol: str = "XAUUSDm"
    timeframe: str = "1m"
    lot: float = 0.01
    leverage: int = 100  # Default 100x (safer for small accounts)
    strategy: str = "xau_hedging"
    sl_pips: float = 500
    tp_pips: float = 1000
    balance: float = 100.0
    days: int = 7
    exchange: Optional[str] = None  # For CCXT: binance, bybit, etc.

    # Trailing stop settings
    trailing_stop: bool = False
    trail_start: float = 500  # pips to start trailing
    break_even: bool = False
    break_even_offset: float = 50  # pips offset for break-even

    # Auto lot sizing
    use_auto_lot: bool = False
    risk_percent: float = 1.0  # Risk per trade (%)

    # Loss limits
    max_daily_loss: float = 100.0
    max_drawdown: float = 20.0  # %

    # Session filters
    use_asia_session: bool = True
    use_london_open: bool = True
    use_ny_session: bool = True

    # API credentials (for live/frontest)
    credentials: Optional[dict] = None

    # Fields that require restart when changed
    RESTART_FIELDS: frozenset = field(
        default_factory=lambda: frozenset(
            {
                "mode",
                "provider",
                "account",
                "symbol",
                "timeframe",
                "strategy",
                "exchange",
                "credentials",
                "days",
            }
        )
    )

    # Fields that can be hot-swapped at runtime
    HOT_SWAP_FIELDS: frozenset = field(
        default_factory=lambda: frozenset(
            {
                "lot",
                "leverage",
                "sl_pips",
                "tp_pips",
                "trailing_stop",
                "trail_start",
                "break_even",
                "break_even_offset",
                "use_asia_session",
                "use_london_open",
                "use_ny_session",
                "use_auto_lot",
                "risk_percent",
                "max_daily_loss",
                "max_drawdown",
            }
        )
    )

    def __post_init__(self):
        # Convert provider string to list if it came from CLI args
        if isinstance(self.provider, str):
            self.provider = [p.strip() for p in self.provider.split(",")]
        elif not self.provider:
            self.provider = ["simulator"]

    def validate(self) -> list:
        """
        Validate configuration settings.

        Returns:
            List of validation error strings (empty if valid)

        Raises:
            ValidationError: If validation fails (use list of errors)
        """
        errors = []

        # Validate mode (paper, frontest, real)
        valid_modes = {"paper", "frontest", "real"}
        if self.mode not in valid_modes:
            errors.append(f"mode must be one of: {', '.join(sorted(valid_modes))}")

        # Validate provider list
        valid_providers = {"simulator", "exness", "ccxt", "ostium"}
        if isinstance(self.provider, str):
            self.provider = [p.strip() for p in self.provider.split(",")]
        elif not self.provider:
            self.provider = ["simulator"]
            
        if isinstance(self.provider, list):
            for p in self.provider:
                if p not in valid_providers:
                    errors.append(
                        f"provider '{p}' must be one of: {', '.join(sorted(valid_providers))}"
                    )
        else:
            errors.append("provider must be a list or string")

        # Validate account
        valid_accounts = {"demo", "real"}
        if self.account not in valid_accounts:
            errors.append(
                f"account must be one of: {', '.join(sorted(valid_accounts))}"
            )

        # Validate symbol
        valid_symbols = {"XAUUSDm", "XAUUSD", "BTCUSDT", "ETHUSDT", "GBPUSD", "EURUSD"}
        if self.symbol not in valid_symbols:
            errors.append(f"symbol must be one of: {', '.join(sorted(valid_symbols))}")

        # Validate strategy
        valid_strategies = {
            "xau_hedging",
            "grid",
            "trend",
            "hft",
            "scalping",
            "mean_reversion",
            "momentum",
            "breakout",
            "arbitrage",
        }
        if self.strategy not in valid_strategies:
            errors.append(
                f"strategy must be one of: {', '.join(sorted(valid_strategies))}"
            )

        # Validate balance (>= 0)
        if not isinstance(self.balance, (int, float)):
            try:
                self.balance = float(self.balance)
            except (ValueError, TypeError):
                errors.append("balance must be a valid number")

        if self.balance < 0:
            errors.append("balance must be >= 0")

        # Validate days (1-365)
        if not isinstance(self.days, int):
            try:
                self.days = int(self.days)
            except (ValueError, TypeError):
                errors.append("days must be a valid integer")

        if self.days < 1 or self.days > 365:
            errors.append("days must be between 1 and 365")

        # Validate leverage (10-5000)
        if not isinstance(self.leverage, int):
            try:
                self.leverage = int(self.leverage)
            except (ValueError, TypeError):
                errors.append("leverage must be a valid integer")

        if self.leverage < 10 or self.leverage > 5000:
            errors.append("leverage must be between 10 and 5000")

        # Validate lot (0.001-100)
        if not isinstance(self.lot, (int, float)):
            try:
                self.lot = float(self.lot)
            except (ValueError, TypeError):
                errors.append("lot must be a valid number")

        if self.lot < 0.001 or self.lot > 100:
            errors.append("lot must be between 0.001 and 100")

        # Validate sl_pips (0-10000)
        if not isinstance(self.sl_pips, (int, float)):
            try:
                self.sl_pips = float(self.sl_pips)
            except (ValueError, TypeError):
                errors.append("sl_pips must be a valid number")

        if self.sl_pips < 0 or self.sl_pips > 10000:
            errors.append("sl_pips must be between 0 and 10000")

        # Validate tp_pips (0-10000)
        if not isinstance(self.tp_pips, (int, float)):
            try:
                self.tp_pips = float(self.tp_pips)
            except (ValueError, TypeError):
                errors.append("tp_pips must be a valid number")

        if self.tp_pips < 0 or self.tp_pips > 10000:
            errors.append("tp_pips must be between 0 and 10000")

        # DEPENDENCY VALIDATION: TP should be > SL for long positions
        # But we allow both 0 (disabled) for flexibility
        # Check if both are set but TP <= SL (potential issue)
        if self.sl_pips > 0 and self.tp_pips > 0 and self.tp_pips <= self.sl_pips:
            errors.append(
                "tp_pips should be greater than sl_pips for proper risk/reward"
            )

        # Validate trail_start (0-10000)
        if not isinstance(self.trail_start, (int, float)):
            try:
                self.trail_start = float(self.trail_start)
            except (ValueError, TypeError):
                errors.append("trail_start must be a valid number")

        if self.trail_start < 0 or self.trail_start > 10000:
            errors.append("trail_start must be between 0 and 10000")

        # Validate break_even_offset (0-10000)
        if not isinstance(self.break_even_offset, (int, float)):
            try:
                self.break_even_offset = float(self.break_even_offset)
            except (ValueError, TypeError):
                errors.append("break_even_offset must be a valid number")

        if self.break_even_offset < 0 or self.break_even_offset > 10000:
            errors.append("break_even_offset must be between 0 and 10000")

        # Validate risk_percent (0.1-100)
        if not isinstance(self.risk_percent, (int, float)):
            try:
                self.risk_percent = float(self.risk_percent)
            except (ValueError, TypeError):
                errors.append("risk_percent must be a valid number")

        if self.risk_percent < 0.1 or self.risk_percent > 100:
            errors.append("risk_percent must be between 0.1 and 100")

        # Validate max_daily_loss (>= 0)
        if not isinstance(self.max_daily_loss, (int, float)):
            try:
                self.max_daily_loss = float(self.max_daily_loss)
            except (ValueError, TypeError):
                errors.append("max_daily_loss must be a valid number")

        if self.max_daily_loss < 0:
            errors.append("max_daily_loss must be >= 0")

        # Validate max_drawdown (0-100)
        if not isinstance(self.max_drawdown, (int, float)):
            try:
                self.max_drawdown = float(self.max_drawdown)
            except (ValueError, TypeError):
                errors.append("max_drawdown must be a valid number")

        if self.max_drawdown < 0 or self.max_drawdown > 100:
            errors.append("max_drawdown must be between 0 and 100")

        # DEPENDENCY: Leverage vs Balance validation
        # High leverage with low balance can lead to immediate liquidation
        if self.balance > 0 and self.balance < 1000:
            # For small accounts, warn about high leverage
            max_recommended_leverage = int(
                1000 / self.balance * 10
            )  # Cap at reasonable level
            if self.leverage > max_recommended_leverage:
                errors.append(
                    f"leverage {self.leverage}x too high for ${self.balance} balance "
                    f"(recommended: {max_recommended_leverage}x or less)"
                )

        # DEPENDENCY: Auto-lot requires risk_percent
        if self.use_auto_lot and self.risk_percent <= 0:
            errors.append("use_auto_lot requires risk_percent > 0")

        # DEPENDENCY: Trailing stop requires trail_start > 0
        if self.trailing_stop and self.trail_start <= 0:
            errors.append("trailing_stop requires trail_start > 0")

        # DEPENDENCY: Break-even requires break_even_offset >= 0
        if self.break_even and self.break_even_offset < 0:
            errors.append("break_even requires break_even_offset >= 0")

        # Mode vs Account consistency
        if self.mode == "real" and self.account != "real":
            errors.append("real mode requires account='real', not 'demo'")

        if self.mode == "paper" and self.account == "real":
            errors.append("paper mode should use account='demo'")

        # Credentials validation for live modes
        if self.mode in ("frontest", "real"):
            if self.provider and "exness" in self.provider:
                # Would need credentials check - just validate structure
                if self.credentials is None:
                    errors.append(
                        "exness provider requires credentials for frontest/real mode"
                    )
                elif not isinstance(self.credentials, dict):
                    errors.append("credentials must be a dictionary")

        # Exchange validation for CCXT
        if self.provider and "ccxt" in self.provider:
            if self.exchange is None:
                errors.append(
                    "ccxt provider requires exchange to be specified (e.g., binance, bybit)"
                )

        if errors:
            raise ValidationError("; ".join(errors))

        return errors

    def requires_restart(self) -> bool:
        """
        Check if current settings require a restart to take effect.

        Returns:
            True if any settings require restart, False otherwise
        """
        restart_fields = {
            "mode",
            "provider",
            "account",
            "symbol",
            "strategy",
            "exchange",
            "credentials",
            "days",
        }

        for field_name in restart_fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if field_name == "mode" and value != "paper":
                    return True
                elif field_name == "provider":
                    if value and value != ["simulator"]:
                        return True
                elif field_name == "account" and value != "demo":
                    return True
                elif field_name == "symbol" and value != "XAUUSDm":
                    return True
                elif field_name == "strategy" and value != "xau_hedging":
                    return True
                elif field_name == "exchange" and value is not None:
                    return True
                elif field_name == "credentials" and value is not None:
                    return True
                elif field_name == "days" and value != 7:
                    return True

        return False

    def check_restart_required(self, old_config: "InterfaceConfig") -> dict:
        """
        Check which fields changed between old and new config that require restart.

        Args:
            old_config: Previous InterfaceConfig to compare against

        Returns:
            Dict with 'required' (bool) and 'fields' (list of changed field names)
        """
        changed_fields = []

        for field_name in self.RESTART_FIELDS:
            if hasattr(self, field_name) and hasattr(old_config, field_name):
                old_value = getattr(old_config, field_name)
                new_value = getattr(self, field_name)

                # Handle list comparison for provider
                if field_name == "provider":
                    if set(old_value) != set(new_value):
                        changed_fields.append(field_name)
                elif old_value != new_value:
                    changed_fields.append(field_name)

        return {"required": len(changed_fields) > 0, "fields": changed_fields}

    def get_restart_fields(self) -> dict:
        """
        Get fields that currently require restart with their values.

        Returns:
            Dict of field_name: current_value for fields needing restart
        """
        restart_fields = {}
        field_defaults = {
            "mode": "paper",
            "provider": ["simulator"],
            "account": "demo",
            "symbol": "XAUUSDm",
            "leverage": 2000,
            "strategy": "xau_hedging",
            "exchange": None,
            "credentials": None,
            "days": 7,
        }

        for field_name, default_value in field_defaults.items():
            if hasattr(self, field_name):
                current_value = getattr(self, field_name)
                # Compare with default
                if current_value != default_value:
                    restart_fields[field_name] = current_value

        return restart_fields

    def to_dict(self) -> dict:
        """Convert config to dict, excluding sensitive credentials and class fields"""
        # Fields to exclude (class-level fields, not instance data)
        exclude = {"RESTART_FIELDS", "HOT_SWAP_FIELDS"}
        data = {}
        for key, value in self.__dict__.items():
            if key in exclude:
                continue
            if key == "credentials":
                continue  # Skip credentials for security
            if value is not None:
                data[key] = value
        return data

    def apply_config(self, updates: dict) -> tuple:
        """
        Apply configuration updates to running bot (hot-swap).

        Args:
            updates: Dict of field names and new values to apply

        Returns:
            (success: bool, message: str, applied: list, failed: list)
        """
        applied = []
        failed = []

        for field_name, new_value in updates.items():
            if field_name not in self.HOT_SWAP_FIELDS:
                failed.append(f"{field_name}: requires restart")
                continue

            if not hasattr(self, field_name):
                failed.append(f"{field_name}: unknown field")
                continue

            old_value = getattr(self, field_name)

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

                setattr(self, field_name, new_value)
                applied.append(f"{field_name}: {old_value} -> {new_value}")

            except (ValueError, TypeError) as e:
                failed.append(f"{field_name}: invalid value - {e}")

        if failed:
            success = False
            message = f"Hot-swap partially failed: {len(failed)} error(s)"
        else:
            success = True
            message = f"Hot-swap applied successfully: {len(applied)} setting(s)"

        return success, message, applied, failed

    def get_hot_swap_fields(self) -> dict:
        """
        Get current values of hot-swappable fields.

        Returns:
            Dict of field_name: current_value for hot-swap fields
        """
        hot_swap_values = {}
        for field_name in self.HOT_SWAP_FIELDS:
            if hasattr(self, field_name):
                hot_swap_values[field_name] = getattr(self, field_name)
        return hot_swap_values


# Alias for backward compatibility
BotConfig = InterfaceConfig


def save_config_to_file(config: InterfaceConfig, filepath: str) -> str:
    """
    Save config to a JSON file

    Args:
        config: InterfaceConfig to save
        filepath: Path to save the config

    Returns:
        The filepath that was written to

    Raises:
        ValidationError: If config fails validation
    """
    config.validate()
    os.makedirs(
        os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True
    )
    with open(filepath, "w") as f:
        json.dump(config.to_dict(), f, indent=2)
    return filepath


def load_config_from_file(filepath: str) -> InterfaceConfig:
    """
    Load config from a JSON file

    Args:
        filepath: Path to the config file

    Returns:
        InterfaceConfig instance

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(filepath, "r") as f:
        data = json.load(f)
    return InterfaceConfig(**data)


def validate_safety(config: InterfaceConfig) -> tuple:
    """
    Validate config safety and return warnings

    Args:
        config: InterfaceConfig to validate

    Returns:
        (is_safe: bool, warnings: str)
    """
    warnings = []

    # Check lot size for $100 account
    if config.balance <= 100:
        if config.lot >= 0.1:
            warnings.append(
                f"Dangerous lot {config.lot} for ${config.balance} account - could liquidate"
            )
        elif config.lot >= 0.05:
            warnings.append(
                f"High lot {config.lot} for ${config.balance} account - 25%+ risk"
            )

    # Check leverage
    if config.leverage < 100:
        warnings.append(f"Low leverage {config.leverage}x - may not be effective")

    # Real mode checks - always warn about real trading
    if config.mode == "real":
        if config.account != "real":
            warnings.append("Real mode requires real account, not demo")
        else:
            warnings.append("Real mode: real money at risk")
        if config.lot > 0.02:
            warnings.append("High lot size in real mode - consider starting smaller")

    # Determine safety
    is_safe = len(warnings) == 0

    return is_safe, "; ".join(warnings) if warnings else ""


class BaseInterface(ABC):
    """Base class for all trading bot interfaces"""

    def __init__(self, config: Optional[InterfaceConfig] = None):
        self.config = config or InterfaceConfig()
        self.running = False
        self.on_start_callback: Optional[Callable] = None
        self.on_stop_callback: Optional[Callable] = None
        self.on_trade_callback: Optional[Callable] = None
        self.on_pause_callback: Optional[Callable] = None
        self.on_resume_callback: Optional[Callable] = None
        self.on_close_all_callback: Optional[Callable] = None
        self.on_close_position_callback: Optional[Callable] = None
        self.on_config_update_callback: Optional[Callable[[dict], None]] = None
        self.on_restart_required_callback: Optional[Callable[[dict], bool]] = None
        self.on_restart_callback: Optional[Callable] = None
        self._original_config: Optional[InterfaceConfig] = None

    def set_callbacks(
        self,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_trade: Optional[Callable] = None,
        on_pause: Optional[Callable] = None,
        on_resume: Optional[Callable] = None,
        on_close_all: Optional[Callable] = None,
        on_close_position: Optional[Callable] = None,
        on_config_update: Optional[Callable[[dict], None]] = None,
        on_restart_required: Optional[Callable[[dict], bool]] = None,
        on_restart: Optional[Callable] = None,
    ):
        """Set callback functions"""
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self.on_trade_callback = on_trade
        self.on_pause_callback = on_pause
        self.on_resume_callback = on_resume
        self.on_close_all_callback = on_close_all
        self.on_close_position_callback = on_close_position
        self.on_config_update_callback = on_config_update
        self.on_restart_required_callback = on_restart_required
        self.on_restart_callback = on_restart

    def apply_config_update(self, updates: dict) -> dict:
        if self.on_config_update_callback:
            result = self.on_config_update_callback(updates)
            if result:
                return result

        if self._original_config is None:
            import copy

            self._original_config = copy.deepcopy(self.config)

        restart_updates = {}
        hot_swap_updates = {}

        for field_name, value in updates.items():
            if field_name in self.config.RESTART_FIELDS:
                restart_updates[field_name] = value
            else:
                hot_swap_updates[field_name] = value

        applied = []
        failed = []
        restart_required = []

        if hot_swap_updates:
            success, message, applied, failed = self.config.apply_config(
                hot_swap_updates
            )

        if restart_updates:
            temp_config = InterfaceConfig(**self.config.to_dict())
            for field_name, value in restart_updates.items():
                setattr(temp_config, field_name, value)

            restart_check = temp_config.check_restart_required(self._original_config)
            if restart_check["required"]:
                restart_required = restart_check["fields"]

            for field_name in restart_updates:
                failed.append(f"{field_name}: requires restart to apply")

        if failed:
            success = False
            message = f"Config update: {len(applied)} applied, {len(failed)} failed"
        else:
            success = True
            message = f"Config updated: {len(applied)} setting(s) applied"

        return {
            "success": success,
            "message": message,
            "applied": applied,
            "failed": failed,
            "restart_required": restart_required,
            "needs_restart": len(restart_required) > 0,
        }

    def request_restart(self, new_config: "InterfaceConfig") -> bool:
        if self.on_restart_required_callback:
            result = self.on_restart_required_callback(new_config.to_dict())
            if result is False:
                return False

        if self.on_stop_callback:
            self.on_stop_callback()

        self.config = new_config
        self._original_config = None

        if self.on_restart_callback:
            self.on_restart_callback()

        return True

    def save_original_config(self):
        import copy

        self._original_config = copy.deepcopy(self.config)

    @abstractmethod
    def run(self):
        """Run the interface"""
        pass

    @abstractmethod
    def stop(self):
        """Stop the interface"""
        pass

    @abstractmethod
    def log(self, message: str, level: str = "info"):
        """Log a message"""
        pass

    @abstractmethod
    def update_metrics(self, metrics: dict):
        """Update displayed metrics"""
        pass
