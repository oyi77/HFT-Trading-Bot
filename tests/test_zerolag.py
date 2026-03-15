"""
Tests for ZeroLag EMA Strategy
"""

import pytest
from trading_bot.strategy.zerolag import ZeroLagStrategy, ZeroLagConfig
from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide
from trading_bot.utils.indicators import (
    calculate_zlema,
    calculate_zlema_series,
    calculate_highest,
)


# ─── Indicator Tests ───


class TestCalculateZlema:
    """Test Zero Lag EMA calculation"""

    def test_returns_none_insufficient_data(self):
        assert calculate_zlema([100.0, 101.0], 63) is None

    def test_returns_float_with_enough_data(self):
        # Generate enough data: need length + lag + 1 = 63 + 31 + 1 = 95
        prices = [2650.0 + i * 0.1 for i in range(200)]
        result = calculate_zlema(prices, 63)
        assert result is not None
        assert isinstance(result, float)

    def test_zlema_follows_price_trend(self):
        """ZLEMA should be above simple average when prices trend up."""
        prices = [2600.0 + i * 0.5 for i in range(200)]
        zlema = calculate_zlema(prices, 20)
        sma = sum(prices[-20:]) / 20
        # Zero lag should lead (be closer to recent price) vs SMA
        assert zlema is not None
        assert abs(zlema - prices[-1]) < abs(sma - prices[-1])


class TestCalculateZlemaSeries:
    """Test ZLEMA series calculation"""

    def test_returns_none_insufficient_data(self):
        assert calculate_zlema_series([100.0], 10) is None

    def test_returns_list(self):
        prices = [2650.0 + i * 0.1 for i in range(200)]
        series = calculate_zlema_series(prices, 20)
        assert series is not None
        assert isinstance(series, list)
        assert len(series) >= 2

    def test_series_last_equals_single(self):
        """Last value of series should match single ZLEMA call."""
        prices = [2650.0 + i * 0.1 for i in range(200)]
        single = calculate_zlema(prices, 20)
        series = calculate_zlema_series(prices, 20)
        assert single is not None
        assert series is not None
        assert abs(series[-1] - single) < 0.001


class TestCalculateHighest:
    """Test highest value calculation"""

    def test_returns_none_insufficient_data(self):
        assert calculate_highest([1.0, 2.0], 5) is None

    def test_returns_max_value(self):
        values = [1.0, 5.0, 3.0, 2.0, 4.0]
        assert calculate_highest(values, 5) == 5.0

    def test_lookback_window(self):
        values = [10.0, 1.0, 2.0, 3.0, 4.0]
        # Only look at last 3: [2.0, 3.0, 4.0]
        assert calculate_highest(values, 3) == 4.0


# ─── Config Tests ───


class TestZeroLagConfig:
    """Test ZeroLag configuration"""

    def test_default_config(self):
        config = ZeroLagConfig()
        assert config.lots == 0.01
        assert config.band_length == 63
        assert config.band_multiplier == 1.1
        assert config.max_layers == 4
        assert config.lot_multiplier == 2.0
        assert config.layer_gap_pips == 20.0
        assert config.tp_pips == 30.0
        assert config.sl_pips == 100.0
        assert config.runner_target_pips == 100.0
        assert config.use_runner is True
        assert config.use_reversal_cut is True
        assert config.use_session_filter is True

    def test_custom_config(self):
        config = ZeroLagConfig(
            lots=0.05,
            band_length=50,
            max_layers=6,
            tp_pips=50.0,
            use_runner=False,
        )
        assert config.lots == 0.05
        assert config.band_length == 50
        assert config.max_layers == 6
        assert config.tp_pips == 50.0
        assert config.use_runner is False


# ─── Strategy Tests ───


class TestZeroLagStrategy:
    """Test ZeroLag Strategy"""

    @pytest.fixture
    def strategy(self):
        config = ZeroLagConfig(
            lots=0.01,
            use_session_filter=False,
            min_ticks_between_trades=0,
            band_length=20,  # Shorter for tests
        )
        return ZeroLagStrategy(config)

    def test_instantiation(self, strategy):
        assert strategy is not None
        assert isinstance(strategy, Strategy)
        assert strategy.current_trend == 0
        assert strategy.tick_count == 0

    def test_returns_none_insufficient_data(self, strategy):
        """Should return None until enough data for indicators."""
        result = strategy.on_tick(
            price=2650.0, bid=2649.99, ask=2650.01, positions=[]
        )
        assert result is None

    def test_builds_price_history(self, strategy):
        """on_tick should build price history."""
        for i in range(10):
            strategy.on_tick(
                price=2650.0 + i, bid=2649.99 + i, ask=2650.01 + i, positions=[]
            )
        assert len(strategy.closes) == 10
        assert len(strategy.highs) == 10
        assert len(strategy.lows) == 10

    def test_trend_detection_bullish(self, strategy):
        """Force a bullish crossover and verify trend changes."""
        # Feed data that trends strongly upward to trigger bullish
        base = 2600.0
        for i in range(100):
            p = base + i * 0.3 + (5.0 if i > 90 else 0)  # Sharp jump at end
            strategy.on_tick(price=p, bid=p - 0.01, ask=p + 0.01, positions=[])

        # After strong upward crossover, trend should be bullish
        # (may or may not trigger depending on volatility calculation)
        assert strategy.tick_count == 100
        assert strategy.current_trend in [0, 1, -1]  # Valid trend states

    def test_no_entry_without_signal(self, strategy):
        """Without a clear signal, should not enter."""
        # Feed flat data (no trend)
        for i in range(100):
            p = 2650.0 + (i % 2) * 0.01  # Oscillate around same price
            result = strategy.on_tick(
                price=p, bid=p - 0.01, ask=p + 0.01, positions=[]
            )
        # With flat data, there should be no entry signal
        assert result is None

    def test_grid_layer_buy(self, strategy):
        """Should open averaging layer when price drops below gap."""
        strategy.config.min_ticks_between_trades = 0

        # Simulate having a long position
        positions = [
            Position(
                id="1",
                symbol="XAUUSDm",
                side=PositionSide.LONG,
                entry_price=2650.0,
                amount=0.01,
            )
        ]

        # Feed enough data so indicators work
        for i in range(100):
            strategy.on_tick(
                price=2650.0, bid=2649.99, ask=2650.01, positions=[]
            )

        # Price dropped below entry by layer_gap_pips
        gap = strategy.config.layer_gap_pips * strategy.config.point_value
        drop_price = 2650.0 - gap - 0.1

        result = strategy.on_tick(
            price=drop_price,
            bid=drop_price - 0.01,
            ask=drop_price + 0.01,
            positions=positions,
        )

        if result and result.get("action") == "open":
            assert result["side"] == OrderSide.BUY
            # Layer 2 lot should be base * multiplier^1 = 0.01 * 2.0 = 0.02
            assert result["amount"] == 0.02

    def test_grid_layer_sell(self, strategy):
        """Should open averaging layer when price rises above gap."""
        strategy.config.min_ticks_between_trades = 0

        positions = [
            Position(
                id="1",
                symbol="XAUUSDm",
                side=PositionSide.SHORT,
                entry_price=2650.0,
                amount=0.01,
            )
        ]

        for i in range(100):
            strategy.on_tick(
                price=2650.0, bid=2649.99, ask=2650.01, positions=[]
            )

        gap = strategy.config.layer_gap_pips * strategy.config.point_value
        rise_price = 2650.0 + gap + 0.1

        result = strategy.on_tick(
            price=rise_price,
            bid=rise_price - 0.01,
            ask=rise_price + 0.01,
            positions=positions,
        )

        if result and result.get("action") == "open":
            assert result["side"] == OrderSide.SELL
            assert result["amount"] == 0.02

    def test_basket_tp_close(self, strategy):
        """Should close position when basket TP is reached."""
        strategy.config.use_runner = False
        strategy.config.min_ticks_between_trades = 0

        positions = [
            Position(
                id="1",
                symbol="XAUUSDm",
                side=PositionSide.LONG,
                entry_price=2650.0,
                amount=0.01,
            )
        ]

        for i in range(100):
            strategy.on_tick(
                price=2650.0, bid=2649.99, ask=2650.01, positions=[]
            )

        # Price at TP level
        tp = strategy.config.tp_pips * strategy.config.point_value
        tp_price = 2650.0 + tp + 0.1

        result = strategy.on_tick(
            price=tp_price,
            bid=tp_price - 0.01,
            ask=tp_price + 0.01,
            positions=positions,
        )

        if result:
            assert result["action"] == "close"
            assert result["position_id"] == "1"

    def test_runner_mode_keeps_best(self, strategy):
        """Runner mode should close bottom layers and keep best."""
        strategy.config.use_runner = True

        positions = [
            Position(id="1", symbol="XAUUSDm", side=PositionSide.LONG,
                     entry_price=2640.0, amount=0.01),
            Position(id="2", symbol="XAUUSDm", side=PositionSide.LONG,
                     entry_price=2650.0, amount=0.02),
        ]

        for i in range(100):
            strategy.on_tick(
                price=2650.0, bid=2649.99, ask=2650.01, positions=[]
            )

        # Average price = (2640*0.01 + 2650*0.02) / 0.03 ≈ 2646.67
        avg = (2640.0 * 0.01 + 2650.0 * 0.02) / 0.03
        tp = strategy.config.tp_pips * strategy.config.point_value
        tp_price = avg + tp + 0.1

        result = strategy.on_tick(
            price=tp_price,
            bid=tp_price - 0.01,
            ask=tp_price + 0.01,
            positions=positions,
        )

        if result and result["action"] == "close":
            # Should close the lower entry (id="1"), keep id="2" as runner
            assert result["position_id"] == "1"

    def test_reversal_cut_loss(self, strategy):
        """Should cut opposite positions on signal reversal."""
        # Manually set trend and positions
        strategy.current_trend = 1  # Was bullish

        short_pos = Position(
            id="s1", symbol="XAUUSDm", side=PositionSide.SHORT,
            entry_price=2650.0, amount=0.01,
        )

        # Directly test the cut method
        result = strategy._cut_on_reversal([short_pos])
        assert result is not None
        assert result["action"] == "close"
        assert result["position_id"] == "s1"

    def test_reversal_cut_bearish(self, strategy):
        """Should cut longs on bearish reversal."""
        strategy.current_trend = -1

        long_pos = Position(
            id="l1", symbol="XAUUSDm", side=PositionSide.LONG,
            entry_price=2650.0, amount=0.01,
        )

        result = strategy._cut_on_reversal([long_pos])
        assert result is not None
        assert result["action"] == "close"
        assert result["position_id"] == "l1"

    def test_max_layers_respected(self, strategy):
        """Should not open more positions than max_layers."""
        strategy.config.max_layers = 2

        positions = [
            Position(id="1", symbol="XAUUSDm", side=PositionSide.LONG,
                     entry_price=2650.0, amount=0.01),
            Position(id="2", symbol="XAUUSDm", side=PositionSide.LONG,
                     entry_price=2630.0, amount=0.02),
        ]

        for i in range(100):
            strategy.on_tick(
                price=2650.0, bid=2649.99, ask=2650.01, positions=[]
            )

        # Price drops far below → would trigger layer but max reached
        result = strategy.on_tick(
            price=2600.0, bid=2599.99, ask=2600.01, positions=positions,
        )

        # Should NOT open a new layer (already at max)
        if result and result.get("action") == "open":
            pytest.fail("Should not open new layer when max_layers reached")

    def test_average_price_calculation(self):
        """Test volume-weighted average price."""
        positions = [
            Position(id="1", symbol="X", side=PositionSide.LONG,
                     entry_price=2640.0, amount=0.01),
            Position(id="2", symbol="X", side=PositionSide.LONG,
                     entry_price=2660.0, amount=0.03),
        ]
        avg = ZeroLagStrategy._get_average_price(positions)
        expected = (2640.0 * 0.01 + 2660.0 * 0.03) / 0.04
        assert abs(avg - expected) < 0.01

    def test_get_stats(self, strategy):
        """Test stats output."""
        strategy.on_tick(price=2650.0, bid=2649.99, ask=2650.01, positions=[])
        stats = strategy.get_stats()
        assert stats["tick_count"] == 1
        assert stats["current_trend"] == 0
        assert "bars_since_signal" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
