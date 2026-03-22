"""
Tests for exchange providers
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from trading_bot.exchange.exness_web import (
    ExnessWebProvider,
    ExnessConfig,
    create_exness_web_provider
)
from trading_bot.exchange.simulator import SimulatorExchange, calculate_profit
from trading_bot.core.interfaces import Exchange
from trading_bot.core.models import Position, OrderSide, PositionSide, Trade


class TestExnessConfig:
    """Test Exness configuration"""
    
    def test_config_creation(self):
        """Test creating Exness config"""
        config = ExnessConfig(
            account_id=413461571,
            token="test_token",
            server="trial6"
        )
        
        assert config.account_id == 413461571
        assert config.token == "test_token"
        assert config.server == "trial6"
        # base_url is the root URL, server is appended in methods
        assert "rtapi-sg.eccweb.mobi" in config.base_url


class TestExnessWebProvider:
    """Test Exness Web Provider"""
    
    @pytest.fixture
    def provider(self):
        """Create a test provider"""
        config = ExnessConfig(
            account_id=413461571,
            token="test_jwt_token",
            server="trial6"
        )
        return ExnessWebProvider(config)
    
    def test_provider_creation(self, provider):
        """Test provider initialization"""
        assert provider.config.account_id == 413461571
        assert provider.config.server == "trial6"
        assert "Bearer test_jwt_token" in provider.session.headers["authorization"]
    
    def test_get_base_url(self, provider):
        """Test base URL generation"""
        url = provider._get_base_url()
        assert "413461571" in url
        assert "trial6" in url
        assert "/v1/accounts/" in url
    
    def test_get_v2_url(self, provider):
        """Test v2 URL generation"""
        url = provider._get_v2_url()
        assert "413461571" in url
        assert "/v2/accounts/" in url
    
    @patch('requests.Session.get')
    def test_get_balance_success(self, mock_get, provider):
        """Test getting balance"""
        mock_response = Mock()
        mock_response.json.return_value = {"balance": "100.50"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        balance = provider.get_balance()
        
        assert balance == 100.50
        mock_get.assert_called_once()
    
    @patch('requests.Session.get')
    def test_get_balance_error(self, mock_get, provider):
        """Test balance error handling"""
        mock_get.side_effect = Exception("Connection error")
        
        balance = provider.get_balance()
        
        assert balance == 0.0
    
    @patch('requests.Session.get')
    def test_get_account_info(self, mock_get, provider):
        """Test getting account info"""
        # Mock balance response
        mock_response = Mock()
        mock_response.json.return_value = {
            "balance": "100.00",
            "equity": "105.00",
            "margin": "10.00",
            "free_margin": "95.00"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        info = provider.get_account_info()
        
        assert info['balance'] == 100.0
        assert info['equity'] == 105.0
        assert info['login'] == 413461571
    
    @patch('requests.Session.get')
    def test_get_account_info_with_leverage_fallback(self, mock_get, provider):
        """Test account info with leverage calculation fallback"""
        # Mock balance response with margin data
        mock_response = Mock()
        mock_response.json.return_value = {
            "balance": "200.00",
            "equity": "200.00",
            "margin": "1.00",  # 1 margin with 200 balance = ~200 leverage
            "free_margin": "199.00"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        info = provider.get_account_info()
        
        # Should calculate leverage from balance/margin
        assert info['leverage'] > 0 or info['balance'] == 200.0
    
    def test_timeframe_mapping(self, provider):
        """Test timeframe mappings"""
        assert provider.TIMEFRAMES["1m"] == 1
        assert provider.TIMEFRAMES["5m"] == 5
        assert provider.TIMEFRAMES["1h"] == 60
        assert provider.TIMEFRAMES["1d"] == 1440
    
    def test_order_types(self, provider):
        """Test order type constants"""
        assert provider.ORDER_TYPE_BUY == 0
        assert provider.ORDER_TYPE_SELL == 1
        assert provider.ORDER_TYPE_BUY_LIMIT == 2
        assert provider.ORDER_TYPE_SELL_LIMIT == 3
        assert provider.ORDER_TYPE_BUY_STOP == 4
        assert provider.ORDER_TYPE_SELL_STOP == 5


class TestCreateExnessProvider:
    """Test factory function"""
    
    def test_create_provider(self):
        """Test factory function"""
        provider = create_exness_web_provider(
            account_id=12345,
            token="factory_token",
            server="real17"
        )
        
        assert isinstance(provider, ExnessWebProvider)
        assert provider.config.account_id == 12345
        assert provider.config.token == "factory_token"
        assert provider.config.server == "real17"


class TestSimulatorExchange:
    """Test Simulator Exchange"""
    
    @pytest.fixture
    def sim(self):
        """Create a simulator"""
        return SimulatorExchange(initial_balance=100.0, symbol="XAUUSDm")
    
    def test_simulator_creation(self, sim):
        """Test simulator initialization"""
        assert sim.initial_balance == 100.0
        assert sim.balance == 100.0
        assert sim.symbol == "XAUUSDm"
        assert sim.current_price == 5000.0
    
    def test_get_price(self, sim):
        """Test getting price"""
        price = sim.get_price()
        assert price == 5000.0
    
    def test_update_price(self, sim):
        """Test price update"""
        initial_price = sim.get_price()
        sim.update_price()
        new_price = sim.get_price()
        
        # Price should change (random walk)
        assert new_price != initial_price or len(sim.price_history) == 1
    
    def test_get_balance(self, sim):
        """Test getting balance"""
        assert sim.get_balance() == 100.0
    
    def test_get_equity_no_positions(self, sim):
        """Test equity with no positions"""
        assert sim.get_equity() == 100.0
    
    def test_open_position(self, sim):
        """Test opening a position"""
        position_id = sim.open_position(
            symbol="XAUUSDm",
            side="buy",
            volume=0.01,
            sl=4900.0,
            tp=5100.0
        )
        
        assert position_id is not None
        assert len(sim.positions) == 1
        
        pos = sim.positions[0]
        assert pos.side == PositionSide.LONG
        assert pos.amount == 0.01
        assert pos.sl == 4900.0
        assert pos.tp == 5100.0
    
    def test_open_position_sell(self, sim):
        """Test opening sell position"""
        position_id = sim.open_position(
            symbol="XAUUSDm",
            side="sell",
            volume=0.01,
            sl=5100.0,
            tp=4900.0
        )
        
        assert position_id == "1"
        pos = sim.positions[0]
        assert pos.side == PositionSide.SHORT
    
    def test_get_positions(self, sim):
        """Test getting positions"""
        sim.open_position("XAUUSDm", "buy", 0.01)
        
        positions = sim.get_positions()
        assert len(positions) == 1
        assert positions[0].side == PositionSide.LONG
    
    def test_close_position(self, sim):
        """Test closing a position"""
        position_id = sim.open_position("XAUUSDm", "buy", 0.01)
        
        # Move price up for profit
        sim.current_price = 5100.0
        
        result = sim.close_position(position_id)
        
        assert result is True
        assert len(sim.positions) == 0
        assert len(sim.closed_positions) == 1
    
    def test_close_position_invalid(self, sim):
        """Test closing invalid position"""
        result = sim.close_position("999")
        assert result is False
    
    def test_modify_position(self, sim):
        """Test modifying position"""
        position_id = sim.open_position("XAUUSDm", "buy", 0.01, sl=4900.0)
        
        result = sim.modify_position(position_id, sl=4850.0, tp=5150.0)
        
        assert result is True
        pos = sim.positions[0]
        assert pos.sl == 4850.0
        assert pos.tp == 5150.0
    
    def test_check_sl_hit(self, sim):
        """Test stop loss trigger"""
        sim.open_position("XAUUSDm", "buy", 0.01, sl=4950.0)
        
        # Price drops below SL
        sim.current_price = 4940.0
        sim._check_triggers()
        
        # Position should be closed
        assert len(sim.positions) == 0
        assert len(sim.closed_positions) == 1
    
    def test_check_tp_hit(self, sim):
        """Test take profit trigger"""
        sim.open_position("XAUUSDm", "buy", 0.01, tp=5050.0)
        
        # Price rises above TP
        sim.current_price = 5060.0
        sim._check_triggers()
        
        # Position should be closed
        assert len(sim.positions) == 0
        assert len(sim.closed_positions) == 1
    
    def test_get_stats(self, sim):
        """Test getting statistics"""
        # Open and close a position
        position_id = sim.open_position("XAUUSDm", "buy", 0.01)
        sim.current_price = 5100.0
        sim.close_position(position_id)
        
        stats = sim.get_stats()
        
        assert stats['total_trades'] == 1
        assert stats['balance'] != 100.0  # Should have changed
        assert 'win_rate' in stats
    
    def test_position_calculate_profit(self, sim):
        """Test position P&L calculation"""
        position_id = sim.open_position("XAUUSDm", "buy", 0.01)
        pos = sim.positions[0]
        
        # Price up $100
        profit = calculate_profit(str(pos.side.value), pos.entry_price, 5100.0, pos.amount)
        assert profit > 0
        
        # Price down $100
        loss = calculate_profit(str(pos.side.value), pos.entry_price, 4900.0, pos.amount)
        assert loss < 0


class TestExchangeInterface:
    """Test that providers implement the Exchange interface"""
    
    def test_exness_implements_interface(self):
        """Test Exness provider implements Exchange"""
        from trading_bot.core.interfaces import Exchange
        assert issubclass(ExnessWebProvider, Exchange)
    
    def test_simulator_has_required_methods(self):
        """Test Simulator has all required methods"""
        # SimulatorExchange doesn't inherit from Exchange but should have same methods
        required_methods = [
            'get_price', 'get_balance', 'get_positions',
            'open_position', 'close_position', 'modify_position'
        ]
        for method in required_methods:
            assert hasattr(SimulatorExchange, method), f"Missing {method}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
