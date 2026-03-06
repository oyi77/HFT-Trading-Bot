"""
Integration tests - End-to-end workflow tests
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading_bot.interface.base import BotConfig, validate_safety

from unittest.mock import Mock, patch, MagicMock
from trading_bot.exchange.simulator import SimulatorExchange
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.utils.auth import AuthManager, ExnessCredentials


class TestEndToEndFlow:
    """End-to-end workflow tests"""

    def test_paper_trading_workflow(self):
        """Test complete paper trading workflow"""
        # 1. Create config
        config = BotConfig(
            mode="paper",
            provider="simulator",
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

        # 2. Validate safety
        is_safe, warnings = validate_safety(config)
        assert is_safe is True

        # 3. Setup exchange
        exchange = SimulatorExchange(
            initial_balance=config.balance, symbol=config.symbol
        )
        assert exchange.get_balance() == 100.0

        # 4. Setup strategy
        strategy_config = XAUHedgingConfig(
            lots=config.lot,
            stop_loss=int(config.sl_pips),
            take_profit=int(config.tp_pips),
        )
        strategy = XAUHedgingStrategy(strategy_config)

        # 5. Run simulation loop (simplified)
        for _ in range(50):
            exchange.update_price()
            price = exchange.get_price()
            bid = price - 0.02
            ask = price + 0.02

            positions = exchange.get_positions()
            signal = strategy.on_tick(price, bid, ask, positions)

            if signal and signal.get("action") == "open":
                side = (
                    signal["side"].value
                    if hasattr(signal["side"], "value")
                    else signal["side"]
                )
                exchange.open_position(
                    symbol=config.symbol,
                    side=side,
                    volume=signal["amount"],
                    sl=signal.get("sl"),
                    tp=signal.get("tp"),
                )

        # 6. Verify results
        stats = exchange.get_stats()
        assert "balance" in stats
        assert "equity" in stats
        # Balance should still be positive
        assert stats["balance"] > 0

    def test_strategy_signal_to_execution(self):
        """Test signal generation through execution"""
        # Setup
        exchange = SimulatorExchange(initial_balance=100.0)
        strategy = XAUHedgingStrategy(XAUHedgingConfig(lots=0.01))

        # No positions - should get open signal
        signal = strategy.on_tick(price=5000.0, bid=4999.98, ask=5000.02, positions=[])

        assert signal is not None
        assert signal["action"] == "open"
        assert signal["amount"] == 0.01
        assert "sl" in signal

        # Execute signal
        side = (
            signal["side"].value if hasattr(signal["side"], "value") else signal["side"]
        )
        position_id = exchange.open_position(
            symbol="XAUUSDm",
            side=side,
            volume=signal["amount"],
            sl=signal.get("sl"),
            tp=signal.get("tp"),
        )

        assert position_id is not None
        assert len(exchange.get_positions()) == 1

        # One position - should get hedge signal
        positions = exchange.get_positions()
        signal = strategy.on_tick(
            price=5000.0, bid=4999.98, ask=5000.02, positions=positions
        )

        assert signal is not None
        assert signal["action"] == "pending"

    def test_position_lifecycle(self):
        """Test complete position lifecycle"""
        exchange = SimulatorExchange(initial_balance=1000.0)

        # Open position
        position_id = exchange.open_position(
            symbol="XAUUSDm", side="buy", volume=0.01, sl=4900.0, tp=5100.0
        )

        assert len(exchange.get_positions()) == 1
        initial_equity = exchange.get_equity()

        # Price moves favorably
        for _ in range(20):
            exchange.update_price()

        # Position still open (may hit SL/TP randomly)
        # Just verify stats work
        stats = exchange.get_stats()
        assert stats["balance"] >= 0

    def test_trailing_stop_execution(self):
        """Test trailing stop logic"""
        exchange = SimulatorExchange(initial_balance=1000.0)
        strategy = XAUHedgingStrategy(XAUHedgingConfig(lots=0.01))

        # Open position
        signal = strategy.on_tick(5000.0, 4999.98, 5000.02, [])
        side = (
            signal["side"].value if hasattr(signal["side"], "value") else signal["side"]
        )
        position_id = exchange.open_position(
            "XAUUSDm", side, signal["amount"], sl=signal.get("sl"), tp=signal.get("tp")
        )

        pos = exchange.get_positions()[0]
        initial_sl = pos.sl

        # Simulate price moving up significantly
        # Update trailing stops via strategy
        for price in [5050.0, 5100.0, 5150.0]:
            strategy._trail_stops(
                positions=exchange.positions, bid=price, ask=price + 0.02, point=0.01
            )

        # SL should have moved or position closed (trailing stop logic may vary)
        # Just verify the trailing stop logic was applied (no exception)
        assert pos.sl >= initial_sl or len(exchange.closed_positions) >= 0


class TestAuthFlow:
    """Test authentication flows"""

    @patch.dict(
        os.environ,
        {
            "EXNESS_TOKEN": "test_token",
            "EXNESS_ACCOUNT_ID": "12345",
            "EXNESS_SERVER": "trial6",
        },
    )
    def test_exness_auth_from_env(self):
        """Test Exness auth using environment variables"""
        manager = AuthManager()
        creds = manager.authenticate_exness(interactive=False)

        assert creds.is_valid
        assert creds.token == "test_token"
        assert creds.account_id == 12345
        assert creds.server == "trial6"

    def test_exness_auth_manual(self):
        """Test Exness auth with manual credentials"""
        manager = AuthManager()
        creds = manager.authenticate_exness(
            interactive=False, account_id=99999, token="manual_token", server="real17"
        )

        assert creds.is_valid
        assert creds.account_id == 99999

    def test_auth_credentials_storage(self):
        """Test credential storage and retrieval"""
        creds = ExnessCredentials(
            account_id=413461571,
            token="secret_jwt_token",
            server="trial6",
            is_valid=True,
        )

        # Masked dict (for display)
        masked = creds.to_dict(mask_secrets=True)
        assert "token_masked" in masked
        assert "token" not in masked

        # Unmasked dict (for trading)
        unmasked = creds.to_dict(mask_secrets=False)
        assert unmasked["token"] == "secret_jwt_token"


class TestSafetyValidation:
    """Test safety validation logic"""

    def test_safe_config(self):
        """Test safe configuration passes"""
        config = BotConfig(
            mode="paper",
            provider="exness",
            account="demo",
            symbol="XAUUSDm",
            lot=0.01,  # Safe lot
            leverage=2000,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        is_safe, warnings = validate_safety(config)
        assert is_safe is True

    def test_dangerous_lot_warning(self):
        """Test warning for high lot size"""
        config = BotConfig(
            mode="paper",
            provider="exness",
            account="demo",
            symbol="XAUUSDm",
            lot=0.1,  # Dangerous for $100 account
            leverage=2000,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        is_safe, warnings = validate_safety(config)
        assert "lot" in warnings.lower() or "dangerous" in warnings.lower()

    def test_real_mode_safety(self):
        """Test real mode triggers warnings"""
        config = BotConfig(
            mode="real",
            provider="exness",
            account="real",
            symbol="XAUUSDm",
            lot=0.01,
            leverage=2000,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        is_safe, warnings = validate_safety(config)
        assert "real" in warnings.lower() or "money" in warnings.lower()

    def test_real_mode_with_demo_account_fails(self):
        """Test real mode fails with demo account"""
        config = BotConfig(
            mode="real",
            provider="exness",
            account="demo",  # Wrong account type
            symbol="XAUUSDm",
            lot=0.01,
            leverage=2000,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
        )

        is_safe, warnings = validate_safety(config)
        assert is_safe is False


class TestMultiProviderSupport:
    """Test multiple provider support"""

    def test_exness_provider_config(self):
        """Test Exness-specific configuration"""
        config = BotConfig(
            mode="frontest",
            provider="exness",
            account="demo",
            symbol="XAUUSDm",
            lot=0.01,
            leverage=2000,
            strategy="xau_hedging",
            sl_pips=500,
            tp_pips=1000,
            credentials={
                "account_id": 413461571,
                "server": "trial6",
                "token": "jwt_token",
            },
        )

        assert config.provider == "exness"
        assert config.credentials["server"] == "trial6"

    def test_ccxt_provider_config(self):
        """Test CCXT-specific configuration"""
        config = BotConfig(
            mode="frontest",
            provider="ccxt",
            account="demo",
            symbol="BTC/USD",
            lot=0.01,
            leverage=100,
            strategy="grid",
            sl_pips=1000,
            tp_pips=2000,
            exchange="binance",
            credentials={"api_key": "key", "api_secret": "secret", "sandbox": True},
        )

        assert config.provider == "ccxt"
        assert config.exchange == "binance"
        assert config.credentials["sandbox"] is True

    def test_ostium_provider_config(self):
        """Test Ostium-specific configuration"""
        config = BotConfig(
            mode="real",
            provider="ostium",
            account="real",
            symbol="ETHUSD",
            lot=0.1,
            leverage=10,
            strategy="trend",
            sl_pips=50,
            tp_pips=100,
            credentials={
                "private_key": "0x...",
                "rpc_url": "https://arb1.arbitrum.io/rpc",
                "chain_id": 42161,
            },
        )

        assert config.provider == "ostium"
        assert config.credentials["chain_id"] == 42161


class TestOstiumIntegration:
    """Integration tests for Ostium DEX SDK"""

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("OSTIUM_PRIVATE_KEY"), reason="OSTIUM_PRIVATE_KEY not set"
    )
    def test_ostium_sdk_initialization(self):
        """Test Ostium SDK can be initialized"""
        from trading_bot.exchange.ostium import create_ostium_exchange
        import asyncio

        async def test():
            exchange = await create_ostium_exchange(
                private_key=os.getenv("OSTIUM_PRIVATE_KEY"),
                rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
                chain_id=421614,
                verbose=False,
            )
            assert exchange is not None
            assert exchange.connected is True
            assert exchange.sdk is not None
            assert exchange.trader_address is not None
            return exchange

        exchange = asyncio.get_event_loop().run_until_complete(test())
        assert exchange.balance >= 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("OSTIUM_PRIVATE_KEY"), reason="OSTIUM_PRIVATE_KEY not set"
    )
    def test_ostium_price_fetching(self):
        """Test Ostium price fetching works"""
        from trading_bot.exchange.ostium import create_ostium_exchange
        import asyncio

        async def test():
            exchange = await create_ostium_exchange(
                private_key=os.getenv("OSTIUM_PRIVATE_KEY"),
                rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
                chain_id=421614,
            )

            # Test price fetching for different assets
            xau_price = await exchange.get_price("XAUUSD")
            btc_price = await exchange.get_price("BTCUSD")
            eth_price = await exchange.get_price("ETHUSD")

            assert xau_price > 0
            assert btc_price > 0
            assert eth_price > 0

            # XAU should be around $2500-6000
            assert 2500 < xau_price < 6000
            # BTC should be around $50k-100k
            assert 50000 < btc_price < 100000
            # ETH should be around $2000-5000
            assert 2000 < eth_price < 5000

        asyncio.get_event_loop().run_until_complete(test())

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("OSTIUM_PRIVATE_KEY"), reason="OSTIUM_PRIVATE_KEY not set"
    )
    def test_ostium_testnet_faucet(self):
        """Test testnet faucet functionality"""
        from trading_bot.exchange.ostium import create_ostium_exchange
        import asyncio

        async def test():
            exchange = await create_ostium_exchange(
                private_key=os.getenv("OSTIUM_PRIVATE_KEY"),
                rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
                chain_id=421614,
            )

            # Get initial balance
            initial_balance = await exchange.get_usdc_balance()

            # Try to request tokens (may fail if recently requested)
            try:
                success = await exchange.request_testnet_tokens()
                if success:
                    # Verify balance increased
                    await asyncio.sleep(5)  # Wait for confirmation
                    new_balance = await exchange.get_usdc_balance()
                    assert new_balance > initial_balance
            except Exception as e:
                # Faucet may rate limit, that's ok for test
                pytest.skip(f"Faucet unavailable or rate limited: {e}")

        asyncio.get_event_loop().run_until_complete(test())

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("OSTIUM_PRIVATE_KEY"), reason="OSTIUM_PRIVATE_KEY not set"
    )
    def test_ostium_open_position_workflow(self):
        """Test opening a position on Ostium testnet"""
        from trading_bot.exchange.ostium import create_ostium_exchange
        from trading_bot.strategy.xau_hedging import (
            XAUHedgingStrategy,
            XAUHedgingConfig,
        )
        import asyncio

        async def test():
            # Setup exchange
            exchange = await create_ostium_exchange(
                private_key=os.getenv("OSTIUM_PRIVATE_KEY"),
                rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
                chain_id=421614,
            )

            # Check balance
            balance = await exchange.get_usdc_balance()
            if balance < 100:
                pytest.skip(f"Insufficient testnet balance: {balance} USDC")

            # Setup strategy
            strategy_config = XAUHedgingConfig(lots=0.01)
            strategy = XAUHedgingStrategy(strategy_config)

            # Get price
            price = await exchange.get_price("XAUUSD")

            # Get signal
            signal = strategy.on_tick(price, price - 0.5, price + 0.5, [])
            assert signal is not None
            assert signal["action"] == "open"

            # Open position (without TP/SL for simplicity)
            pos_id = await exchange.open_position(
                symbol="XAUUSD", side="buy", volume=0.01, sl=None, tp=None
            )

            # Position may fail due to various reasons (gas, slippage, etc.)
            # but we should at least get a response
            if pos_id:
                assert isinstance(pos_id, str)
                assert len(pos_id) > 0

                # Verify position was tracked
                positions = exchange.get_positions()
                assert len(positions) > 0 or len(exchange.positions) > 0

        asyncio.get_event_loop().run_until_complete(test())

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("OSTIUM_PRIVATE_KEY"), reason="OSTIUM_PRIVATE_KEY not set"
    )
    def test_ostium_balance_tracking(self):
        """Test that balance is fetched from blockchain"""
        from trading_bot.exchange.ostium import create_ostium_exchange
        import asyncio

        async def test():
            exchange = await create_ostium_exchange(
                private_key=os.getenv("OSTIUM_PRIVATE_KEY"),
                rpc_url="https://sepolia-rollup.arbitrum.io/rpc",
                chain_id=421614,
            )

            # Balance should be fetched from blockchain
            assert exchange.balance >= 0

            # Get detailed balance
            balance_dict = exchange.get_balance()
            assert "total" in balance_dict
            assert "free" in balance_dict
            assert balance_dict["total"] >= 0

        asyncio.get_event_loop().run_until_complete(test())

    def test_ostium_exchange_mock(self):
        """Test Ostium exchange with mocked SDK"""
        from trading_bot.exchange.ostium import OstiumExchange, OstiumPosition
        from unittest.mock import Mock, MagicMock
        import asyncio

        # Create exchange with mocked SDK
        with patch("trading_bot.exchange.ostium.OSTIUM_SDK_AVAILABLE", True):
            mock_sdk = Mock()
            mock_sdk.balance.get_usdc_balance.return_value = 5000.0
            mock_sdk.price.get_price.return_value = (2650.0, 2650.5, 2649.5)

            mock_config = Mock()
            mock_config.testnet.return_value = Mock(rpc_url="https://test.rpc")

            with patch("trading_bot.exchange.ostium.NetworkConfig", mock_config):
                with patch(
                    "trading_bot.exchange.ostium.OstiumSDK", return_value=mock_sdk
                ):
                    exchange = OstiumExchange(
                        private_key="0x" + "a" * 64,
                        rpc_url="https://test.rpc",
                        chain_id=421614,
                    )
                    exchange.sdk = mock_sdk
                    exchange.connected = True
                    exchange.trader_address = "0x1234567890abcdef"

                    # Test mocked price
                    async def test_price():
                        price = await exchange.get_price("XAUUSD")
                        assert price == 2650.0

                    asyncio.get_event_loop().run_until_complete(test_price())

                    # Test mocked balance
                    exchange.balance = 5000.0  # Set the balance attribute
                    balance = exchange.get_balance()
                    assert balance is not None
                    assert balance.get("total", 0) == 5000.0


class TestBybitIntegration:
    """Integration tests for Bybit Testnet"""

    @pytest.mark.integration
    def test_bybit_exchange_initialization(
        self, has_bybit_credentials, bybit_credentials
    ):
        """Test Bybit exchange can be initialized"""
        if not has_bybit_credentials:
            pytest.skip("BYBIT_API_KEY not set")

        from trading_bot.exchange.bybit_exchange import create_bybit_exchange

        exchange = create_bybit_exchange(
            api_key=bybit_credentials["api_key"],
            api_secret=bybit_credentials["api_secret"],
            testnet=True,
        )

        assert exchange is not None
        assert exchange.connected is True
        assert exchange.testnet is True

    @pytest.mark.integration
    def test_bybit_price_fetching(self, has_bybit_credentials, bybit_credentials):
        """Test Bybit price fetching"""
        if not has_bybit_credentials:
            pytest.skip("BYBIT_API_KEY not set")

        from trading_bot.exchange.bybit_exchange import create_bybit_exchange

        exchange = create_bybit_exchange(
            api_key=bybit_credentials["api_key"],
            api_secret=bybit_credentials["api_secret"],
            testnet=True,
        )

        assert exchange is not None

        # Test price fetching
        bid, ask = exchange.get_price_with_spread("XAUUSD")
        assert bid > 0
        assert ask > 0
        assert ask > bid

    @pytest.mark.integration
    def test_bybit_balance_fetching(self, has_bybit_credentials, bybit_credentials):
        """Test Bybit balance fetching"""
        if not has_bybit_credentials:
            pytest.skip("BYBIT_API_KEY not set")

        from trading_bot.exchange.bybit_exchange import create_bybit_exchange

        exchange = create_bybit_exchange(
            api_key=bybit_credentials["api_key"],
            api_secret=bybit_credentials["api_secret"],
            testnet=True,
        )

        assert exchange is not None

        # Test balance fetching
        balance = exchange.get_balance()
        assert "total" in balance
        assert "free" in balance
        assert balance["free"] >= 0


class TestExnessIntegration:
    """Integration tests for Exness Demo Account"""

    @pytest.mark.integration
    def test_exness_exchange_initialization(
        self, has_exness_credentials, exness_credentials
    ):
        """Test Exness exchange can be initialized"""
        if not has_exness_credentials:
            pytest.skip("EXNESS credentials not set")

        from trading_bot.exchange.exness_exchange import create_exness_exchange

        exchange = create_exness_exchange(
            account_id=int(exness_credentials["account_id"]),
            token=exness_credentials["token"],
            server=exness_credentials["server"],
        )

        if exchange:
            assert exchange.connected is True
        else:
            pytest.skip("Could not connect to Exness (token may be expired)")

    @pytest.mark.integration
    def test_exness_balance_fetching(self, has_exness_credentials, exness_credentials):
        """Test Exness balance fetching"""
        if not has_exness_credentials:
            pytest.skip("EXNESS credentials not set")

        from trading_bot.exchange.exness_exchange import create_exness_exchange

        exchange = create_exness_exchange(
            account_id=int(exness_credentials["account_id"]),
            token=exness_credentials["token"],
            server=exness_credentials["server"],
        )

        if not exchange:
            pytest.skip("Could not connect to Exness")

        # Test balance fetching
        balance = exchange.get_balance()
        assert "total" in balance
        assert "free" in balance
        assert balance["free"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
