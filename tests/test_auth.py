"""
Tests for authentication utilities
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from trading_bot.utils.auth import (
    AuthManager,
    ExnessCredentials,
    CCXTCredentials,
    OstiumCredentials,
    quick_auth
)


class TestExnessCredentials:
    """Test Exness credential handling"""
    
    def test_exness_credentials_creation(self):
        """Test creating Exness credentials"""
        creds = ExnessCredentials(
            account_id=413461571,
            token="eyJhbGciOiJSUzI1NiIs...test_token",
            server="trial6",
            is_valid=True
        )
        
        assert creds.provider == "exness"
        assert creds.account_id == 413461571
        assert creds.token == "eyJhbGciOiJSUzI1NiIs...test_token"
        assert creds.server == "trial6"
        assert creds.is_valid is True
    
    def test_exness_credentials_to_dict_masked(self):
        """Test credential masking for display"""
        creds = ExnessCredentials(
            account_id=413461571,
            token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test",
            server="trial6",
            is_valid=True
        )
        
        result = creds.to_dict(mask_secrets=True)
        assert "token_masked" in result
        assert result["token_masked"].endswith("...")
        assert "token" not in result
    
    def test_exness_credentials_to_dict_unmasked(self):
        """Test credential without masking"""
        creds = ExnessCredentials(
            account_id=413461571,
            token="secret_token_123",
            server="trial6",
            is_valid=True
        )
        
        result = creds.to_dict(mask_secrets=False)
        assert result["token"] == "secret_token_123"
        assert "token_masked" not in result


class TestAuthManager:
    """Test AuthManager functionality"""
    
    def test_auth_manager_initialization(self):
        """Test AuthManager creation"""
        manager = AuthManager()
        assert manager.credentials is None
    
    @patch.dict(os.environ, {
        'EXNESS_TOKEN': 'env_token_123',
        'EXNESS_ACCOUNT_ID': '12345',
        'EXNESS_SERVER': 'real17'
    })
    def test_authenticate_exness_from_env(self):
        """Test Exness auth from environment variables"""
        manager = AuthManager()
        creds = manager.authenticate_exness(interactive=False)
        
        assert creds.is_valid is True
        assert creds.token == 'env_token_123'
        assert creds.account_id == 12345
        assert creds.server == 'real17'
    
    def test_authenticate_exness_from_params(self):
        """Test Exness auth from passed parameters"""
        manager = AuthManager()
        creds = manager.authenticate_exness(
            interactive=False,
            account_id=99999,
            token="param_token",
            server="trial5"
        )
        
        assert creds.is_valid is True
        assert creds.token == "param_token"
        assert creds.account_id == 99999
        assert creds.server == "trial5"
    
    def test_authenticate_exness_missing_token(self):
        """Test Exness auth fails without token"""
        # Clear env vars
        with patch.dict(os.environ, {}, clear=True):
            manager = AuthManager()
            creds = manager.authenticate_exness(interactive=False)
            
            assert creds.is_valid is False
            assert "token" in creds.error_message.lower() or "missing" in creds.error_message.lower()
    
    @patch.dict(os.environ, {
        'EXCHANGE_NAME': 'binance',
        'EXCHANGE_API_KEY': 'api_key_123',
        'EXCHANGE_API_SECRET': 'api_secret_456'
    })
    def test_authenticate_ccxt_from_env(self):
        """Test CCXT auth from environment"""
        manager = AuthManager()
        creds = manager.authenticate_ccxt(interactive=False)
        
        assert creds.is_valid is True
        assert creds.exchange == 'binance'
        assert creds.api_key == 'api_key_123'
        assert creds.api_secret == 'api_secret_456'
    
    def test_authenticate_ccxt_from_params(self):
        """Test CCXT auth from parameters"""
        manager = AuthManager()
        creds = manager.authenticate_ccxt(
            interactive=False,
            exchange='bybit',
            api_key='key123',
            api_secret='secret456',
            sandbox=True
        )
        
        assert creds.is_valid is True
        assert creds.exchange == 'bybit'
        assert creds.sandbox is True


class TestQuickAuth:
    """Test quick_auth convenience function"""
    
    def test_quick_auth_exness(self):
        """Test quick auth for Exness"""
        creds = quick_auth(
            "exness",
            interactive=False,
            account_id=11111,
            token="quick_token",
            server="trial6"
        )
        
        assert isinstance(creds, ExnessCredentials)
        assert creds.account_id == 11111
    
    def test_quick_auth_ccxt(self):
        """Test quick auth for CCXT"""
        creds = quick_auth(
            "ccxt",
            interactive=False,
            exchange="okx",
            api_key="key",
            api_secret="secret"
        )
        
        assert isinstance(creds, CCXTCredentials)
        assert creds.exchange == "okx"
    
    def test_quick_auth_invalid_provider(self):
        """Test quick auth with invalid provider"""
        with pytest.raises(ValueError) as exc_info:
            quick_auth("invalid_provider", interactive=False)
        
        assert "invalid_provider" in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
