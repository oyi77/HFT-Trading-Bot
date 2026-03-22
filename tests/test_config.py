"""
Tests for configuration handling
"""

import json
import os
import sys
import tempfile
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from trading_bot.interface.base
from trading_bot.interface.base import (
    BotConfig,
    load_config_from_file,
    save_config_to_file,
)


class TestBotConfig:
    """Test BotConfig dataclass"""

    def test_default_config(self):
        """Test config with default values"""
        config = BotConfig(
            mode="paper",
            provider=["exness"],
            account="demo",
            symbol="XAUUSDm",
            lot=0.01,
            leverage=100,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        assert config.mode == "paper"
        assert config.provider == ["exness"]
        assert config.account == "demo"
        assert config.symbol == "XAUUSDm"
        assert config.lot == 0.01
        assert config.leverage == 100
        assert config.strategy == "xau_hedging"
        assert config.sl_pips == 500
        assert config.tp_pips == 1000
        # Check defaults
        assert config.days == 7
        assert config.balance == 100.0
        assert config.exchange is None
        assert config.credentials is None

    def test_custom_config(self):
        """Test config with custom values"""
        config = BotConfig(
            mode="frontest",
            provider=["ccxt"],
            account="demo",
            symbol="BTCUSD",
            lot=0.02,
            leverage=100,
            strategy="grid",
            sl_pips=300,
            tp_pips=600,
            days=14,
            balance=500.0,
            exchange="binance",
            credentials={"api_key": "test"},
        )

        assert config.mode == "frontest"
        assert config.provider == ["ccxt"]
        assert config.exchange == "binance"
        assert config.balance == 500.0
        assert config.days == 14

    def test_config_to_dict(self):
        """Test config serialization"""
        config = BotConfig(
            mode="paper",
            provider=["exness"],
            account="demo",
            symbol="XAUUSDm",
            lot=0.01,
            leverage=100,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
            credentials={"token": "secret"},
        )

        data = config.to_dict()

        # Credentials should be excluded
        assert "credentials" not in data
        assert data["mode"] == "paper"
        assert data["symbol"] == "XAUUSDm"

    def test_config_all_modes(self):
        """Test config for all trading modes"""
        modes = ["paper", "frontest", "real"]

        for mode in modes:
            config = BotConfig(
                mode=mode,
                provider=["exness"],
                account="real" if mode == "real" else "demo",
                symbol="XAUUSDm",
                lot=0.01,
                leverage=100,
                strategy="xau_hedging",
                sl_pips=500,
                tp_pips=1000,
            )
            assert config.mode == mode


class TestConfigFileOperations:
    """Test loading and saving config files"""

    def test_save_and_load_config(self, tmp_path):
        """Test saving and loading config"""
        config = BotConfig(
            mode="paper",
            provider=["exness"],
            account="demo",
            symbol="XAUUSDm",
            lot=0.01,
            leverage=100,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
            days=7,
            balance=100.0,
        )

        filepath = tmp_path / "test_config.json"

        # Save
        result = save_config_to_file(config, str(filepath))
        assert os.path.exists(result)

        # Load
        loaded = load_config_from_file(str(filepath))

        assert loaded.mode == config.mode
        assert loaded.symbol == config.symbol
        assert loaded.lot == config.lot

    def test_load_nonexistent_config(self):
        """Test loading non-existent config"""
        with pytest.raises(FileNotFoundError):
            load_config_from_file("/nonexistent/path/config.json")

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON"""
        filepath = tmp_path / "invalid.json"
        filepath.write_text("not valid json")

        with pytest.raises(json.JSONDecodeError):
            load_config_from_file(str(filepath))


class TestConfigValidation:
    """Test config validation scenarios"""

    def test_high_lot_warning(self):
        """Test config with dangerous lot size"""
        config = BotConfig(
            mode="paper",
            provider=["exness"],
            account="demo",
            symbol="XAUUSDm",
            lot=0.1,  # High lot
            leverage=100,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        assert config.lot == 0.1
        # 0.1 lot with 500 pip SL = $500 risk

    def test_low_leverage_warning(self):
        """Test config with low leverage"""
        config = BotConfig(
            mode="paper",
            provider=["exness"],
            account="demo",
            symbol="XAUUSDm",
            lot=0.01,
            leverage=50,  # Low leverage
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        assert config.leverage == 50

    def test_real_mode_requires_real_account(self):
        """Test real mode config"""
        config = BotConfig(
            mode="real",
            provider=["exness"],
            account="real",  # Must be real
            symbol="XAUUSDm",
            lot=0.01,
            leverage=100,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        assert config.mode == "real"
        assert config.account == "real"

    def test_ccxt_config(self):
        """Test CCXT-specific config"""
        config = BotConfig(
            mode="frontest",
            provider=["ccxt"],
            account="demo",
            symbol="BTC/USD",
            lot=0.01,
            leverage=100,
            strategy="grid",
            sl_pips=1000,
            tp_pips=2000,
            exchange="binance",
            credentials={
                "api_key": "test_key",
                "api_secret": "test_secret",
                "sandbox": True,
            },
        )

        assert config.provider == ["ccxt"]
        assert config.exchange == "binance"
        creds = config.credentials
        assert creds is not None and creds.get("sandbox") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
