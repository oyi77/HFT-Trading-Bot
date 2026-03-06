"""
Test PnL key consistency between exchanges and engine
"""

import pytest
from unittest.mock import Mock

from trading_bot.exchange.ostium import OstiumExchange
from trading_bot.exchange.exness_exchange import ExnessExchange


class TestPnLKeyConsistency:
    """Test that all exchanges return 'net_pnl' key for engine compatibility"""

    def test_ostium_returns_net_pnl_key(self):
        """Ostium get_stats must return 'net_pnl' key"""
        exchange = OstiumExchange.__new__(OstiumExchange)
        exchange.balance = 1000.0
        exchange.equity = 1050.0
        exchange.positions = []
        exchange.trades = []

        stats = exchange.get_stats()

        assert "net_pnl" in stats
        assert "total_pnl" in stats
        assert stats["net_pnl"] == stats["total_pnl"]

    def test_exness_returns_net_pnl_key(self):
        """Exness get_stats must return 'net_pnl' key"""
        exchange = ExnessExchange.__new__(ExnessExchange)
        exchange.balance = 1000.0
        exchange.equity = 1050.0
        exchange.positions = []
        exchange.trades = []
        exchange.connected = False
        exchange.provider = None

        stats = exchange.get_stats()

        assert "net_pnl" in stats
        assert "total_pnl" in stats
        assert stats["net_pnl"] == stats["total_pnl"]

    def test_pnl_calculation_with_positions(self):
        """PnL should be calculated from position unrealized_pnl"""
        from trading_bot.exchange.ostium import OstiumPosition

        exchange = OstiumExchange.__new__(OstiumExchange)
        exchange.balance = 1000.0
        exchange.positions = [
            OstiumPosition(
                id="1",
                symbol="XAUUSD",
                side="long",
                size=0.1,
                entry_price=5000.0,
                current_price=5100.0,
                unrealized_pnl=10.0,
                leverage=10,
                liquidation_price=4500.0,
                margin=50.0,
                pair_id=5,
                trade_index=1,
            ),
            OstiumPosition(
                id="2",
                symbol="XAUUSD",
                side="short",
                size=0.05,
                entry_price=5200.0,
                current_price=5100.0,
                unrealized_pnl=5.0,
                leverage=10,
                liquidation_price=5700.0,
                margin=25.0,
                pair_id=5,
                trade_index=2,
            ),
        ]
        exchange.trades = []

        stats = exchange.get_stats()

        assert stats["net_pnl"] == 15.0  # 10 + 5
        assert stats["total_pnl"] == 15.0
        assert stats["equity"] == 1015.0  # 1000 + 15
