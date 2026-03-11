"""
Test Exness real-time metrics updates
"""

import pytest
from unittest.mock import Mock

from trading_bot.exchange.exness_exchange import ExnessExchange


class TestExnessRealtimeMetrics:
    """Test that Exness metrics are fetched in real-time"""

    def test_get_stats_fetches_live_balance(self):
        """get_stats should fetch fresh balance/equity from provider"""
        exchange = ExnessExchange.__new__(ExnessExchange)
        exchange.connected = True
        exchange.positions = []
        exchange.trades = []

        # Mock provider with changing balance
        mock_provider = Mock()
        mock_provider.get_balance.return_value = 150.0
        mock_provider.get_equity.return_value = 155.5
        exchange.provider = mock_provider

        # Initial cached values
        exchange.balance = 100.0
        exchange.equity = 105.0

        # Call get_stats
        stats = exchange.get_stats()

        # Should fetch from provider
        mock_provider.get_balance.assert_called_once()
        mock_provider.get_equity.assert_called_once()

        # Should return updated values
        assert stats["balance"] == 150.0
        assert stats["equity"] == 155.5

    def test_get_stats_uses_cached_when_disconnected(self):
        """get_stats should use cached values when not connected"""
        exchange = ExnessExchange.__new__(ExnessExchange)
        exchange.connected = False
        exchange.positions = []
        exchange.trades = []
        exchange.provider = None

        # Cached values
        exchange.balance = 100.0
        exchange.equity = 105.0

        # Call get_stats
        stats = exchange.get_stats()

        # Should return cached values
        assert stats["balance"] == 100.0
        assert stats["equity"] == 105.0


class TestXAUHedgingMaxPositions:
    """Test max 2 positions limit per ahdu.mq5 spec"""

    def test_strategy_returns_none_when_two_positions_exist(self):
        """Strategy should not open more than 2 positions"""
        from trading_bot.strategy.xau_hedging import (
            XAUHedgingStrategy,
            XAUHedgingConfig,
        )
        from trading_bot.core.models import Position, PositionSide

        strategy = XAUHedgingStrategy(XAUHedgingConfig(use_session_filter=False))

        # Create 2 positions
        positions = [
            Position(
                id="1",
                symbol="XAUUSD",
                side=PositionSide.LONG,
                entry_price=5000.0,
                amount=0.01,
            ),
            Position(
                id="2",
                symbol="XAUUSD",
                side=PositionSide.SHORT,
                entry_price=5100.0,
                amount=0.01,
            ),
        ]

        # Strategy should return None (no signal)
        signal = strategy.on_tick(
            price=5050.0, bid=5049.98, ask=5050.02, positions=positions
        )

        assert signal is None

    def test_strategy_opens_main_when_no_positions(self):
        """Strategy should open main position when no positions exist"""
        from trading_bot.strategy.xau_hedging import (
            XAUHedgingStrategy,
            XAUHedgingConfig,
        )

        strategy = XAUHedgingStrategy(XAUHedgingConfig(use_session_filter=False))

        signal = strategy.on_tick(price=5050.0, bid=5049.98, ask=5050.02, positions=[])

        assert signal is not None
        assert signal["action"] == "open"

    def test_strategy_creates_hedge_when_one_position(self):
        """Strategy should create hedge pending when 1 position exists"""
        from trading_bot.strategy.xau_hedging import (
            XAUHedgingStrategy,
            XAUHedgingConfig,
        )
        from trading_bot.core.models import Position, PositionSide

        strategy = XAUHedgingStrategy(XAUHedgingConfig(use_session_filter=False))

        positions = [
            Position(
                id="1",
                symbol="XAUUSD",
                side=PositionSide.LONG,
                entry_price=5000.0,
                amount=0.01,
                sl=4900.0,
            ),
        ]

        signal = strategy.on_tick(
            price=5050.0, bid=5049.98, ask=5050.02, positions=positions
        )

        assert signal is not None
        assert signal["action"] == "pending"
