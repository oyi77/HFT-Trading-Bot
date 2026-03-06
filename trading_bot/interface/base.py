"""
Base interface class for trading bot
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class InterfaceConfig:
    """Configuration for interfaces"""

    mode: str = "paper"
    provider: str = "exness"
    account: str = "demo"  # demo or real
    symbol: str = "XAUUSDm"
    lot: float = 0.01
    leverage: int = 2000
    strategy: str = "xau_hedging"
    sl_pips: float = 500
    tp_pips: float = 1000
    balance: float = 100.0
    days: int = 7
    exchange: Optional[str] = None  # For CCXT: binance, bybit, etc.

    # API credentials (for live/frontest)
    credentials: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert config to dict, excluding sensitive credentials"""
        data = {}
        for key, value in self.__dict__.items():
            if key == "credentials":
                continue  # Skip credentials for security
            if value is not None:
                data[key] = value
        return data


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
    """
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

    def set_callbacks(
        self,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_trade: Optional[Callable] = None,
    ):
        """Set callback functions"""
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self.on_trade_callback = on_trade

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
