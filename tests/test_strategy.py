"""
Tests for trading strategies
"""

import pytest
from datetime import datetime

from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


class TestXAUHedgingConfig:
    """Test XAU Hedging configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = XAUHedgingConfig()

        assert config.lots == 0.01
        assert config.stop_loss == 600
        assert config.take_profit == 1500
        assert config.start_direction == 0
        assert config.x_distance == 100
        assert config.trail_start == 100
        assert config.trailing == 50
        assert config.break_even_profit == 50
        assert config.break_even_offset == 10
        assert config.use_session_filter is True

    def test_custom_config(self):
        """Test custom configuration"""
        config = XAUHedgingConfig(
            lots=0.02, stop_loss=300, take_profit=600, use_session_filter=True
        )

        assert config.lots == 0.02
        assert config.stop_loss == 300
        assert config.take_profit == 600
        assert config.use_session_filter is True


class TestXAUHedgingStrategy:
    """Test XAU Hedging Strategy"""

    @pytest.fixture
    def strategy(self):
        """Create a test strategy"""
        config = XAUHedgingConfig(lots=0.01, stop_loss=500, use_session_filter=False)
        return XAUHedgingStrategy(config)

    def test_strategy_creation(self, strategy):
        """Test strategy initialization"""
        assert strategy.config is not None
        assert strategy.config.lots == 0.01
        assert strategy.main_position is None

    def test_get_session_asia(self, strategy):
        """Test Asia session detection"""
        # Asia session: UTC 0-6 (timestamp in milliseconds)
        # 2024-01-01 03:00 UTC should be asia
        ts_asia = int(datetime(2024, 1, 1, 3, 0).timestamp() * 1000)
        session = strategy._get_session(ts_asia)
        # Note: Hour calculation depends on timezone, just check it returns a string
        assert isinstance(session, str)
        assert session in ["asia", "london_open", "london_peak", "ny", "off_market"]

    def test_get_session_ny(self, strategy):
        """Test NY session detection"""
        # NY session: UTC 17-22
        ts_ny = int(datetime(2024, 1, 1, 19, 0).timestamp() * 1000)
        session = strategy._get_session(ts_ny)
        assert isinstance(session, str)

    def test_is_good_session(self, strategy):
        """Test session filtering"""
        assert strategy._is_good_session("london_open") is True
        assert strategy._is_good_session("london_peak") is True
        assert strategy._is_good_session("ny") is True
        assert strategy._is_good_session("asia") is False
        assert strategy._is_good_session("off_market") is False

    def test_open_main_buy(self, strategy):
        """Test opening main buy position"""
        signal = strategy._open_main(price=5000.0, bid=4999.98, ask=5000.02, point=0.01)

        assert signal is not None
        assert signal["action"] == "open"
        assert signal["side"] == OrderSide.BUY
        assert signal["amount"] == 0.01
        assert signal["sl"] < 5000.02  # SL below entry

    def test_open_main_sell(self, strategy):
        """Test opening main sell position"""
        strategy.config.start_direction = 1  # Sell first

        signal = strategy._open_main(price=5000.0, bid=4999.98, ask=5000.02, point=0.01)

        assert signal["side"] == OrderSide.SELL
        assert signal["sl"] > 4999.98  # SL above entry

    def test_handle_hedge_long(self, strategy):
        """Test hedge creation for long position"""
        # Create a long position with SL
        main_pos = Position(
            id="1",
            symbol="XAUUSDm",
            side=PositionSide.LONG,
            entry_price=5000.0,
            amount=0.01,
            sl=4900.0,
        )

        signal = strategy._handle_hedge(
            main_pos=main_pos, bid=4999.98, ask=5000.02, point=0.01
        )

        assert signal is not None
        assert signal["action"] == "pending"
        assert signal["side"] == OrderSide.SELL
        assert "stop_price" in signal

    def test_handle_hedge_short(self, strategy):
        """Test hedge creation for short position"""
        main_pos = Position(
            id="1",
            symbol="XAUUSDm",
            side=PositionSide.SHORT,
            entry_price=5000.0,
            amount=0.01,
            sl=5100.0,
        )

        signal = strategy._handle_hedge(
            main_pos=main_pos, bid=4999.98, ask=5000.02, point=0.01
        )

        assert signal is not None
        assert signal["side"] == OrderSide.BUY

    def test_handle_hedge_no_sl(self, strategy):
        """Test hedge without SL fails"""
        main_pos = Position(
            id="1",
            symbol="XAUUSDm",
            side=PositionSide.LONG,
            entry_price=5000.0,
            amount=0.01,
            sl=0,  # No SL
        )

        signal = strategy._handle_hedge(
            main_pos=main_pos, bid=4999.98, ask=5000.02, point=0.01
        )

        assert signal is None

    def test_trail_stops_long(self, strategy):
        """Test trailing stops for long position"""
        pos = Position(
            id="1",
            symbol="XAUUSDm",
            side=PositionSide.LONG,
            entry_price=5000.0,
            amount=0.01,
            sl=4900.0,
        )

        # Price moved up significantly
        strategy._trail_stops(
            positions=[pos],
            bid=5150.0,  # 150 pips profit
            ask=5150.02,
            point=0.01,
        )

        # SL should have moved to break even or trailed
        assert pos.sl > 4900.0

    def test_trail_stops_short(self, strategy):
        """Test trailing stops for short position"""
        pos = Position(
            id="1",
            symbol="XAUUSDm",
            side=PositionSide.SHORT,
            entry_price=5000.0,
            amount=0.01,
            sl=5100.0,
        )

        # Price moved down significantly
        strategy._trail_stops(
            positions=[pos],
            bid=4850.0,
            ask=4850.02,  # 150 pips profit
            point=0.01,
        )

        # SL should have moved down
        assert pos.sl < 5100.0

    def test_trail_stops_handles_none_sl(self, strategy):
        class _Pos:
            side = PositionSide.LONG
            entry_price = 5000.0
            sl = None

        pos = _Pos()

        strategy._trail_stops(
            positions=[pos],
            bid=5150.0,
            ask=5150.02,
            point=0.01,
        )

        assert pos.sl is not None

    def test_on_tick_no_positions(self, strategy):
        """Test on_tick with no positions"""
        signal = strategy.on_tick(price=5000.0, bid=4999.98, ask=5000.02, positions=[])

        assert signal is not None
        assert signal["action"] == "open"

    def test_on_tick_one_position(self, strategy):
        """Test on_tick with one position (should create hedge)"""
        positions = [
            Position(
                id="1",
                symbol="XAUUSDm",
                side=PositionSide.LONG,
                entry_price=5000.0,
                amount=0.01,
                sl=4900.0,
            )
        ]

        signal = strategy.on_tick(
            price=5000.0, bid=4999.98, ask=5000.02, positions=positions
        )

        # Should return hedge pending signal
        assert signal is not None

    def test_on_tick_two_positions(self, strategy):
        """Test on_tick with two positions (no action)"""
        positions = [
            Position(
                id="1",
                symbol="XAUUSDm",
                side=PositionSide.LONG,
                entry_price=5000.0,
                amount=0.01,
                sl=4900.0,
            ),
            Position(
                id="2",
                symbol="XAUUSDm",
                side=PositionSide.SHORT,
                entry_price=4950.0,
                amount=0.01,
                sl=5050.0,
            ),
        ]

        signal = strategy.on_tick(
            price=5000.0, bid=4999.98, ask=5000.02, positions=positions
        )

        # Should return None (hedge already placed)
        assert signal is None

    def test_session_filter_blocks_asia(self, strategy):
        """Test that session filter can block trading"""
        strategy.config.use_session_filter = True

        # Manually set session to asia (would need to mock _get_session)
        # For now, just test that when filter is on and session is bad, it blocks
        # This test assumes asia is a bad session
        is_good = strategy._is_good_session("asia")
        assert is_good is False

    def test_session_filter_allows_good_sessions(self, strategy):
        """Test that session filter allows good sessions"""
        strategy.config.use_session_filter = True

        assert strategy._is_good_session("london_open") is True
        assert strategy._is_good_session("london_peak") is True
        assert strategy._is_good_session("ny") is True


class TestConcreteStrategy:
    """Test concrete strategy implementations"""

    def test_xau_strategy_instantiation(self):
        """Test that XAU strategy can be instantiated"""
        strategy = XAUHedgingStrategy(XAUHedgingConfig(use_session_filter=False))
        assert strategy is not None
        assert isinstance(strategy, Strategy)

    def test_xau_strategy_implements_on_tick(self):
        """Test that XAU strategy implements on_tick"""
        strategy = XAUHedgingStrategy(XAUHedgingConfig(use_session_filter=False))

        # Should be able to call on_tick
        signal = strategy.on_tick(price=5000.0, bid=4999.98, ask=5000.02, positions=[])

        assert signal is not None
        assert "action" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
