"""Config persistence for trading bot."""

import json
import os
import shutil
import tempfile
from typing import Optional

from trading_bot.interface.base import InterfaceConfig

CONFIG_VERSION = 1
CONFIG_FILENAME = "config.json"


def get_config_path(filename: str = CONFIG_FILENAME) -> str:
    """Auto-discover config file location."""
    home_config = os.path.expanduser(f"~/.trading-bot/{filename}")
    if os.path.exists(home_config):
        return home_config

    project_config = os.path.join(os.getcwd(), "config", filename)
    if os.path.exists(project_config):
        return project_config

    return home_config


def get_config_dir() -> str:
    """Get config directory, creating if needed."""
    config_dir = os.path.expanduser("~/.trading-bot")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def _prepare_config_data(config: InterfaceConfig) -> dict:
    """Prepare config for JSON with version field."""
    data = config.to_dict()
    data.pop("RESTART_FIELDS", None)
    data["config_version"] = CONFIG_VERSION
    return data


def save_config(config: InterfaceConfig, filepath: Optional[str] = None) -> str:
    """Save config with atomic write."""
    if filepath is None:
        filepath = get_config_path()

    config_dir = os.path.dirname(filepath)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

    data = _prepare_config_data(config)

    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".json", prefix="config_", dir=config_dir
    )

    try:
        with os.fdopen(temp_fd, "w") as f:
            json.dump(data, f, indent=2)
        shutil.move(temp_path, filepath)
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise IOError(f"Failed to save config: {e}")

    return filepath


def load_config(filepath: Optional[str] = None) -> InterfaceConfig:
    """Load config with version migration."""
    if filepath is None:
        filepath = get_config_path()

    with open(filepath, "r") as f:
        data = json.load(f)

    data = _migrate_config(data)
    data.pop("config_version", None)
    return InterfaceConfig(**data)


def _migrate_config(data: dict) -> dict:
    """Migrate config to current version."""
    version = data.get("config_version", 0)

    if version == CONFIG_VERSION:
        return data

    if version == 0:
        data["trailing_stop"] = data.get("trailing_stop", False)
        data["trail_start"] = data.get("trail_start", 500)
        data["break_even"] = data.get("break_even", False)
        data["break_even_offset"] = data.get("break_even_offset", 50)
        data["use_auto_lot"] = data.get("use_auto_lot", False)
        data["risk_percent"] = data.get("risk_percent", 1.0)
        data["max_daily_loss"] = data.get("max_daily_loss", 100.0)
        data["max_drawdown"] = data.get("max_drawdown", 20.0)
        data["use_asia_session"] = data.get("use_asia_session", True)
        data["use_london_open"] = data.get("use_london_open", True)
        data["use_ny_session"] = data.get("use_ny_session", True)
        data["config_version"] = 1

    return data


def config_exists(filepath: Optional[str] = None) -> bool:
    """Check if config file exists."""
    if filepath is None:
        filepath = get_config_path()
    return os.path.exists(filepath)


def delete_config(filepath: Optional[str] = None) -> bool:
    """Delete config file."""
    if filepath is None:
        filepath = get_config_path()

    if os.path.exists(filepath):
        os.unlink(filepath)
        return True
    return False
