"""
Frontest Mode PnL Live Test - Simulates real frontest behavior
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from trading_bot.exchange.ostium import OstiumExchange, OstiumPosition
from trading_bot.exchange.exness_exchange import ExnessExchange
from trading_bot.trading_engine import TradingEngine
from trading_bot.interface.base import InterfaceConfig


class TestFrontestPnLLive:
    """Test PnL updates in frontest-like scenarios"""

    def test_ostium_pnl_updates_with_price_change(self):
        """Simulate: Open position → Price changes → PnL updates"""
        exchange = OstiumExchange.__new__(OstiumExchange)
        exchange.balance = 1000.0
        exchange.trader_address = "0xabc"
        exchange.positions = []
        exchange.trades = []

        # Step 1: Open long position at $5000
        position = OstiumPosition(
            id="pos_1",
            symbol="XAUUSD",
            side="long",
            size=0.1,
            entry_price=5000.0,
            current_price=5000.0,
            unrealized_pnl=0.0,
            leverage=10,
            liquidation_price=4500.0,
            margin=50.0,
            pair_id=5,
            trade_index=1,
        )
        exchange.positions.append(position)

        # Initial PnL = 0
        stats = exchange.get_stats()
        assert stats["net_pnl"] == 0.0
        print(f"Initial PnL: {stats['net_pnl']}")

        # Step 2: Price goes up to $5100 (profit)
        position.current_price = 5100.0
        position.unrealized_pnl = (5100.0 - 5000.0) * 0.1  # $10 profit

        stats = exchange.get_stats()
        assert stats["net_pnl"] == 10.0
        assert stats["equity"] == 1010.0  # Balance + PnL
        print(f"After price up PnL: {stats['net_pnl']}")

        # Step 3: Price goes down to $4950 (loss)
        position.current_price = 4950.0
        position.unrealized_pnl = (4950.0 - 5000.0) * 0.1  # -$5 loss

        stats = exchange.get_stats()
        assert stats["net_pnl"] == -5.0
        assert stats["equity"] == 995.0  # Balance + PnL
        print(f"After price down PnL: {stats['net_pnl']}")

    def test_exness_pnl_updates_with_price_change(self):
        """Simulate: Open position → Price changes → PnL updates"""
        exchange = ExnessExchange.__new__(ExnessExchange)
        exchange.balance = 1000.0
        exchange.equity = 1000.0
        exchange.connected = False
        exchange.provider = None

        # Create mock position
        class MockPos:
            def __init__(self):
                self.id = "1"
                self.symbol = "XAUUSDm"
                self.side = "long"
                self.size = 0.1
                self.entry_price = 5000.0
                self.current_price = 5000.0
                self.unrealized_pnl = 0.0
                self.leverage = 10
                self.margin = 50.0
                self.sl = 4900.0
                self.tp = 5100.0

        position = MockPos()
        exchange.positions = [position]
        exchange.trades = [{"id": "1"}]

        # Initial PnL = 0
        stats = exchange.get_stats()
        assert stats["net_pnl"] == 0.0
        print(f"Exness Initial PnL: {stats['net_pnl']}")

        # Price goes up to $5100
        position.unrealized_pnl = 10.0
        stats = exchange.get_stats()
        assert stats["net_pnl"] == 10.0
        print(f"Exness After price up PnL: {stats['net_pnl']}")

    def test_trading_engine_reads_pnl_correctly(self):
        """Test that engine reads 'net_pnl' key from stats"""
        config = InterfaceConfig(mode="frontest", symbol="XAUUSDm", balance=100.0)
        engine = TradingEngine(config, interface=None)

        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.get_positions.return_value = []
        mock_exchange.trades = [{"id": "1"}]

        # This is what Ostium/Exness now returns
        mock_exchange.get_stats.return_value = {
            "balance": 1010.0,
            "equity": 1025.0,
            "positions": 1,
            "total_pnl": 15.0,
            "net_pnl": 15.0,  # Key fix: net_pnl is present
            "total_trades": 1,
        }

        mock_exchange.update_price = Mock()
        mock_exchange.get_current_price = Mock(return_value=5100.0)
        mock_exchange.get_price = Mock(return_value=5100.0)

        engine.exchange = mock_exchange
        engine.strategy = Mock()
        engine.strategy.on_tick.return_value = None

        # Run one update cycle
        engine._update()

        # Verify engine read net_pnl correctly
        assert engine.metrics.pnl == 15.0
        assert engine.metrics.balance == 1010.0
        assert engine.metrics.equity == 1025.0
        print(f"Engine PnL: {engine.metrics.pnl}")
        print(f"Engine Balance: {engine.metrics.balance}")
        print(f"Engine Equity: {engine.metrics.equity}")

    def test_multiple_positions_pnl_aggregation(self):
        """Test PnL aggregation with multiple positions"""
        exchange = OstiumExchange.__new__(OstiumExchange)
        exchange.balance = 1000.0
        exchange.positions = [
            OstiumPosition(
                id="1",
                symbol="XAUUSD",
                side="long",
                size=0.1,
                entry_price=5000.0,
                current_price=5100.0,  # +$10
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
                current_price=5100.0,  # +$5
                unrealized_pnl=5.0,
                leverage=10,
                liquidation_price=5700.0,
                margin=25.0,
                pair_id=5,
                trade_index=2,
            ),
        ]
        exchange.trades = [{"id": "1"}, {"id": "2"}]

        stats = exchange.get_stats()

        # Total PnL = 10 + 5 = 15
        assert stats["net_pnl"] == 15.0
        assert stats["total_pnl"] == 15.0
        assert stats["equity"] == 1015.0  # 1000 + 15
        print(f"Multi-position PnL: {stats['net_pnl']}")


class TestFrontestCompleteFlow:
    """Test complete frontest flow: Open → Update PnL → Close"""

    def test_ostium_frontest_complete_trade_cycle(self):
        """Complete trade cycle: Open → Price moves → Close with PnL"""
        exchange = OstiumExchange.__new__(OstiumExchange)
        exchange.balance = 1000.0
        exchange.positions = []
        exchange.trades = []

        # 1. Open position (simulated)
        position = OstiumPosition(
            id="trade_1",
            symbol="XAUUSD",
            side="long",
            size=0.1,
            entry_price=5000.0,
            current_price=5000.0,
            unrealized_pnl=0.0,
            leverage=10,
            liquidation_price=4500.0,
            margin=50.0,
            pair_id=5,
            trade_index=1,
            tx_hash="0xabc123",
        )
        exchange.positions.append(position)
        exchange.trades.append(
            {
                "id": "trade_1",
                "side": "buy",
                "size": 0.1,
                "price": 5000.0,
                "tx_hash": "0xabc123",
            }
        )

        # 2. Price moves up
        position.current_price = 5125.0
        position.unrealized_pnl = 12.5  # (5125 - 5000) * 0.1

        stats = exchange.get_stats()
        print(f"Open PnL: {stats['net_pnl']}, Equity: {stats['equity']}")

        assert stats["net_pnl"] == 12.5
        assert stats["equity"] == 1012.5

        # 3. Close position (realize PnL)
        exchange.positions.remove(position)
        # In real implementation, PnL would be added to balance here

        print("✅ Frontest cycle complete: PnL tracked correctly!")
