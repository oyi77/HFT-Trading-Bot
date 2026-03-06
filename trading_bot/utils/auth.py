"""
Authentication Manager for different exchange providers
Handles login/auth flows for Exness, CCXT (Binance, etc), and Ostium
"""
import os
import json
from typing import Optional, Dict, Any, Tuple
from getpass import getpass
from dataclasses import dataclass


@dataclass
class AuthCredentials:
    """Base auth credentials"""
    provider: str
    is_valid: bool = False
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (without sensitive data)"""
        return {"provider": self.provider, "is_valid": self.is_valid}


@dataclass
class ExnessCredentials(AuthCredentials):
    """Exness Web Trading API credentials"""
    provider: str = "exness"
    account_id: Optional[int] = None
    token: Optional[str] = None
    server: Optional[str] = None
    is_valid: bool = False
    error_message: str = ""
    
    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Convert to dict. Use mask_secrets=False to get actual token."""
        result = {
            "provider": self.provider,
            "is_valid": self.is_valid,
            "account_id": self.account_id,
            "server": self.server,
        }
        if mask_secrets:
            result["token_masked"] = f"{self.token[:20]}..." if self.token and len(self.token) > 20 else None
        else:
            result["token"] = self.token
        return result


@dataclass
class CCXTCredentials(AuthCredentials):
    """CCXT exchange credentials (Binance, Bybit, etc)"""
    provider: str = "ccxt"
    exchange: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None  # For some exchanges like KuCoin
    sandbox: bool = True  # Default to sandbox/testnet
    is_valid: bool = False
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "is_valid": self.is_valid,
            "exchange": self.exchange,
            "api_key_masked": f"{self.api_key[:8]}..." if self.api_key and len(self.api_key) > 8 else None,
            "sandbox": self.sandbox
        }


@dataclass
class OstiumCredentials(AuthCredentials):
    """Ostium DEX credentials"""
    provider: str = "ostium"
    private_key: Optional[str] = None
    rpc_url: Optional[str] = None
    chain_id: Optional[int] = None
    is_valid: bool = False
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "is_valid": self.is_valid,
            "rpc_url": self.rpc_url,
            "chain_id": self.chain_id,
            "private_key_masked": "***" if self.private_key else None
        }


class AuthManager:
    """
    Manages authentication for different exchange providers
    """
    
    # Environment variable mappings
    ENV_MAPPINGS = {
        "exness": {
            "token": "EXNESS_TOKEN",
            "account_id": "EXNESS_ACCOUNT_ID",
            "server": "EXNESS_SERVER"
        },
        "ccxt": {
            "api_key": "EXCHANGE_API_KEY",
            "api_secret": "EXCHANGE_API_SECRET",
            "passphrase": "EXCHANGE_PASSPHRASE",
            "exchange": "EXCHANGE_NAME"  # e.g., "binance", "bybit"
        },
        "ostium": {
            "private_key": "OSTIUM_PRIVATE_KEY",
            "rpc_url": "OSTIUM_RPC_URL",
            "chain_id": "OSTIUM_CHAIN_ID"
        }
    }
    
    def __init__(self):
        self.credentials: Optional[AuthCredentials] = None
    
    def authenticate_exness(self, interactive: bool = True, 
                           account_id: Optional[int] = None,
                           token: Optional[str] = None,
                           server: Optional[str] = None) -> ExnessCredentials:
        """
        Authenticate with Exness Web Trading API
        
        Priority:
        1. Passed parameters
        2. Environment variables
        3. Interactive prompts (if enabled)
        """
        creds = ExnessCredentials()
        
        # Try environment variables first if not provided
        if not token:
            token = os.getenv(self.ENV_MAPPINGS["exness"]["token"])
        if not account_id:
            account_id_str = os.getenv(self.ENV_MAPPINGS["exness"]["account_id"])
            if account_id_str:
                account_id = int(account_id_str)
        if not server:
            server = os.getenv(self.ENV_MAPPINGS["exness"]["server"], "trial6")
        
        # Interactive prompts if still missing and interactive mode
        if interactive:
            print("\n" + "=" * 60)
            print("🔐 EXNESS AUTHENTICATION")
            print("=" * 60)
            print("Provider: Exness Web Trading API")
            print("Mode: JWT Token Authentication")
            print("-" * 60)
            
            if not account_id:
                account_id_input = input("Account ID [413461571]: ").strip()
                account_id = int(account_id_input) if account_id_input else 413461571
            else:
                print(f"Account ID: {account_id}")
            
            if not server:
                server = input("Server [trial6]: ").strip() or "trial6"
            else:
                print(f"Server: {server}")
            
            if not token:
                print("\nJWT Token (input hidden for security):")
                print("  - Get from Exness Personal Area > Web Trading")
                print("  - Or from browser DevTools > Application > Local Storage")
                token = getpass("Token: ").strip()
            else:
                print(f"Token: {'*' * 20}... (from environment)")
        
        creds.account_id = account_id
        creds.token = token
        creds.server = server
        creds.is_valid = bool(token and account_id)
        
        if not creds.is_valid:
            creds.error_message = "Missing token or account_id"
        
        self.credentials = creds
        return creds
    
    def authenticate_ccxt(self, interactive: bool = True,
                         exchange: Optional[str] = None,
                         api_key: Optional[str] = None,
                         api_secret: Optional[str] = None,
                         passphrase: Optional[str] = None,
                         sandbox: bool = True) -> CCXTCredentials:
        """
        Authenticate with CCXT-supported exchange (Binance, Bybit, etc)
        
        Priority:
        1. Passed parameters
        2. Environment variables
        3. Interactive prompts (if enabled)
        """
        creds = CCXTCredentials()
        
        # Try environment variables
        if not exchange:
            exchange = os.getenv(self.ENV_MAPPINGS["ccxt"]["exchange"])
        if not api_key:
            api_key = os.getenv(self.ENV_MAPPINGS["ccxt"]["api_key"])
        if not api_secret:
            api_secret = os.getenv(self.ENV_MAPPINGS["ccxt"]["api_secret"])
        if not passphrase:
            passphrase = os.getenv(self.ENV_MAPPINGS["ccxt"]["passphrase"])
        
        # Interactive prompts
        if interactive:
            print("\n" + "=" * 60)
            print("🔐 CCXT EXCHANGE AUTHENTICATION")
            print("=" * 60)
            print("Supports: Binance, Bybit, OKX, KuCoin, etc.")
            print("-" * 60)
            
            if not exchange:
                exchange = input("Exchange name [binance]: ").strip() or "binance"
            print(f"Exchange: {exchange}")
            
            if not api_key:
                print("\nAPI Key (get from exchange API management):")
                api_key = getpass("API Key: ").strip()
            else:
                print(f"API Key: {'*' * 8}... (from environment)")
            
            if not api_secret:
                print("\nAPI Secret:")
                api_secret = getpass("API Secret: ").strip()
            else:
                print(f"API Secret: {'*' * 8}... (from environment)")
            
            # Passphrase for exchanges that need it
            if exchange.lower() in ["kucoin", "okx"] and not passphrase:
                print("\nPassphrase (required for this exchange):")
                passphrase = getpass("Passphrase: ").strip()
            
            # Sandbox mode confirmation
            if sandbox:
                print("\n⚠️  SANDBOX/TESTNET MODE ENABLED")
                print("   (Safe for testing - no real money)")
                confirm = input("Use sandbox? [Y/n]: ").strip().lower()
                sandbox = confirm in ["", "y", "yes"]
        
        creds.exchange = exchange
        creds.api_key = api_key
        creds.api_secret = api_secret
        creds.passphrase = passphrase
        creds.sandbox = sandbox
        creds.is_valid = bool(exchange and api_key and api_secret)
        
        if not creds.is_valid:
            creds.error_message = "Missing exchange, api_key, or api_secret"
        
        self.credentials = creds
        return creds
    
    def authenticate_ostium(self, interactive: bool = True,
                           private_key: Optional[str] = None,
                           rpc_url: Optional[str] = None,
                           chain_id: Optional[int] = None) -> OstiumCredentials:
        """
        Authenticate with Ostium DEX
        
        Ostium is a decentralized exchange on blockchain
        Requires private key for signing transactions
        """
        creds = OstiumCredentials()
        
        # Try environment variables
        if not private_key:
            private_key = os.getenv(self.ENV_MAPPINGS["ostium"]["private_key"])
        if not rpc_url:
            rpc_url = os.getenv(self.ENV_MAPPINGS["ostium"]["rpc_url"], "https://arb1.arbitrum.io/rpc")
        if not chain_id:
            chain_id_str = os.getenv(self.ENV_MAPPINGS["ostium"]["chain_id"])
            chain_id = int(chain_id_str) if chain_id_str else 42161  # Arbitrum
        
        # Interactive prompts
        if interactive:
            print("\n" + "=" * 60)
            print("🔐 OSTIUM DEX AUTHENTICATION")
            print("=" * 60)
            print("Provider: Ostium (Decentralized Exchange)")
            print("⚠️  WARNING: Never share your private key!")
            print("-" * 60)
            
            if not private_key:
                print("\nPrivate Key (input hidden):")
                print("  - Get from wallet (MetaMask, etc.)")
                print("  - Or create new wallet for trading")
                private_key = getpass("Private Key: ").strip()
            else:
                print(f"Private Key: {'*' * 10} (from environment)")
            
            if not rpc_url:
                rpc_url = input(f"RPC URL [{rpc_url}]: ").strip() or rpc_url
            print(f"RPC URL: {rpc_url}")
            
            if not chain_id:
                chain_id_input = input(f"Chain ID [{chain_id}]: ").strip()
                chain_id = int(chain_id_input) if chain_id_input else chain_id
            print(f"Chain ID: {chain_id} (Arbitrum)")
        
        creds.private_key = private_key
        creds.rpc_url = rpc_url
        creds.chain_id = chain_id
        creds.is_valid = bool(private_key and rpc_url and chain_id)
        
        if not creds.is_valid:
            creds.error_message = "Missing private_key, rpc_url, or chain_id"
        
        self.credentials = creds
        return creds
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection with current credentials
        Returns (success, message)
        """
        if not self.credentials or not self.credentials.is_valid:
            return False, "No valid credentials"
        
        provider = self.credentials.provider
        
        try:
            if provider == "exness":
                from trading_bot.exchange.exness_web import create_exness_web_provider
                creds = self.credentials
                provider_obj = create_exness_web_provider(
                    account_id=creds.account_id,
                    token=creds.token,
                    server=creds.server
                )
                info = provider_obj.get_account_info()
                return True, f"Connected to Exness account {info.get('login', creds.account_id)}"
            
            elif provider == "ccxt":
                # Would need to import CCXT and test
                return True, f"CCXT credentials configured for {self.credentials.exchange}"
            
            elif provider == "ostium":
                # Would need Ostium SDK to test
                return True, "Ostium credentials configured"
            
            else:
                return False, f"Unknown provider: {provider}"
                
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def save_to_file(self, filepath: str, include_secrets: bool = False):
        """Save credentials to file (optionally without secrets)"""
        if not self.credentials:
            raise ValueError("No credentials to save")
        
        data = self.credentials.to_dict()
        
        if include_secrets and hasattr(self.credentials, '__dict__'):
            # Save with secrets (be careful!)
            data = self.credentials.__dict__.copy()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_env(cls, provider: str) -> Optional[AuthCredentials]:
        """Load credentials from environment variables only"""
        manager = cls()
        
        if provider == "exness":
            return manager.authenticate_exness(interactive=False)
        elif provider == "ccxt":
            return manager.authenticate_ccxt(interactive=False)
        elif provider == "ostium":
            return manager.authenticate_ostium(interactive=False)
        
        return None


# Convenience function for quick auth
def quick_auth(provider: str, interactive: bool = True, **kwargs) -> AuthCredentials:
    """
    Quick authentication for a provider
    
    Examples:
        # Exness
        creds = quick_auth("exness")
        creds = quick_auth("exness", account_id=12345, token="...")
        
        # CCXT/Binance
        creds = quick_auth("ccxt", exchange="binance")
        
        # Ostium
        creds = quick_auth("ostium")
    """
    manager = AuthManager()
    
    if provider == "exness":
        return manager.authenticate_exness(
            interactive=interactive,
            account_id=kwargs.get("account_id"),
            token=kwargs.get("token"),
            server=kwargs.get("server")
        )
    elif provider == "ccxt":
        return manager.authenticate_ccxt(
            interactive=interactive,
            exchange=kwargs.get("exchange"),
            api_key=kwargs.get("api_key"),
            api_secret=kwargs.get("api_secret"),
            passphrase=kwargs.get("passphrase"),
            sandbox=kwargs.get("sandbox", True)
        )
    elif provider == "ostium":
        return manager.authenticate_ostium(
            interactive=interactive,
            private_key=kwargs.get("private_key"),
            rpc_url=kwargs.get("rpc_url"),
            chain_id=kwargs.get("chain_id")
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
