"""
Pytest configuration and fixtures
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Custom markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "network: Tests requiring network")


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide test data directory"""
    return os.path.join(os.path.dirname(__file__), "data")


@pytest.fixture
def mock_exness_response():
    """Mock Exness API response"""
    return {
        "balance": "100.00",
        "equity": "105.00",
        "margin": "10.00",
        "free_margin": "95.00",
        "margin_level": 1050.0,
    }


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    from trading_bot import BotConfig

    return BotConfig(
        mode="paper",
        provider="exness",
        account="demo",
        symbol="XAUUSDm",
        lot=0.01,
        leverage=2000,
        strategy="xau_hedging",
        sl_pips=500,
        tp_pips=1000,
        balance=100.0,
        days=1,
    )


@pytest.fixture
def sample_position():
    """Sample position for testing"""
    from trading_bot.core.models import Position, PositionSide

    return Position(
        id="1",
        symbol="XAUUSDm",
        side=PositionSide.LONG,
        entry_price=5000.0,
        volume=0.01,
        sl=4900.0,
        tp=5100.0,
    )


# Environment variable fixtures for integration tests
@pytest.fixture(scope="session")
def ostium_credentials():
    """Ostium testnet credentials"""
    return {
        "private_key": os.getenv("OSTIUM_PRIVATE_KEY"),
        "rpc_url": os.getenv(
            "OSTIUM_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc"
        ),
        "chain_id": int(os.getenv("OSTIUM_CHAIN_ID", "421614")),
    }


@pytest.fixture(scope="session")
def exness_credentials():
    """Exness demo account credentials"""
    return {
        "account_id": os.getenv("EXNESS_ACCOUNT_ID"),
        "token": os.getenv("EXNESS_TOKEN"),
        "server": os.getenv("EXNESS_SERVER", "trial6"),
    }


@pytest.fixture(scope="session")
def bybit_credentials():
    """Bybit testnet credentials"""
    return {
        "api_key": os.getenv("BYBIT_API_KEY"),
        "api_secret": os.getenv("BYBIT_API_SECRET"),
        "testnet": True,
    }


@pytest.fixture(scope="session")
def has_ostium_credentials():
    """Check if Ostium credentials are available"""
    return bool(os.getenv("OSTIUM_PRIVATE_KEY"))


@pytest.fixture(scope="session")
def has_exness_credentials():
    """Check if Exness credentials are available"""
    return bool(os.getenv("EXNESS_ACCOUNT_ID") and os.getenv("EXNESS_TOKEN"))


@pytest.fixture(scope="session")
def has_bybit_credentials():
    """Check if Bybit credentials are available"""
    return bool(os.getenv("BYBIT_API_KEY") and os.getenv("BYBIT_API_SECRET"))
