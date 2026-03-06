# Integration Testing Guide

## Overview

This trading bot supports multiple exchanges for frontest (demo) trading. Integration tests verify real connectivity and basic operations with each exchange's testnet/demo environment.

## Supported Exchanges

### 1. Ostium (Arbitrum Sepolia Testnet)
Decentralized perpetual trading on Arbitrum L2.

**Credentials Needed:**
```bash
export OSTIUM_PRIVATE_KEY="your_ethereum_private_key"
export OSTIUM_RPC_URL="https://sepolia-rollup.arbitrum.io/rpc"  # Optional
export OSTIUM_CHAIN_ID="421614"  # Optional
```

**Test Command:**
```bash
export OSTIUM_PRIVATE_KEY="your_key"
python -m pytest tests/test_integration.py::TestOstiumIntegration -v
```

**Features Tested:**
- SDK initialization
- Price fetching from oracle
- Testnet faucet (USDC)
- Opening positions on-chain
- Balance tracking

---

### 2. Bybit (Testnet)
Centralized exchange testnet using CCXT.

**Credentials Needed:**
```bash
export BYBIT_API_KEY="your_api_key"
export BYBIT_API_SECRET="your_api_secret"
# Testnet is enabled by default
```

**Get Testnet Credentials:**
1. Sign up at [testnet.bybit.com](https://testnet.bybit.com)
2. Go to API Management
3. Create API key with trading permissions
4. Fund testnet account with test USDT

**Test Command:**
```bash
export BYBIT_API_KEY="your_key"
export BYBIT_API_SECRET="your_secret"
python -m pytest tests/test_integration.py::TestBybitIntegration -v
```

**Features Tested:**
- Exchange initialization
- Price fetching (bid/ask)
- Balance fetching (USDT)

---

### 3. Exness (Demo Account)
Forex/CFD broker demo account.

**Credentials Needed:**
```bash
export EXNESS_ACCOUNT_ID="413461571"
export EXNESS_TOKEN="your_jwt_token"
export EXNESS_SERVER="trial6"  # or trial5, real17, etc.
```

**Get Demo Credentials:**
1. Sign up at [my.exness.com](https://my.exness.com)
2. Open Demo MT5 account
3. Login to Web Terminal
4. Open DevTools (F12) → Network
5. Find API request, copy Bearer token

**Test Command:**
```bash
export EXNESS_ACCOUNT_ID="your_account"
export EXNESS_TOKEN="your_token"
export EXNESS_SERVER="trial6"
python -m pytest tests/test_integration.py::TestExnessIntegration -v
```

**Features Tested:**
- Web API connection
- Balance fetching
- Server connectivity

---

## Running All Integration Tests

### With All Credentials
```bash
# Set all credentials
export OSTIUM_PRIVATE_KEY="..."
export BYBIT_API_KEY="..."
export BYBIT_API_SECRET="..."
export EXNESS_ACCOUNT_ID="..."
export EXNESS_TOKEN="..."

# Run all integration tests
python -m pytest tests/test_integration.py -v -m integration

# Run ALL tests (unit + integration)
python -m pytest tests/ -v
```

### With Specific Exchange Only
```bash
# Only Ostium tests
python -m pytest tests/test_integration.py::TestOstiumIntegration -v

# Only Bybit tests  
python -m pytest tests/test_integration.py::TestBybitIntegration -v

# Only Exness tests
python -m pytest tests/test_integration.py::TestExnessIntegration -v
```

---

## Test Results Summary

Current test count:
- **Unit tests**: ~85 tests (auth, exchange, strategy, config)
- **Integration tests**: 9 tests across 3 exchanges
- **Total**: 94+ tests

### Exchange Test Matrix

| Exchange | Tests | Status | Requirements |
|----------|-------|--------|--------------|
| Ostium | 6 | ✅ Active | Private key |
| Bybit | 3 | ✅ Active | API key/secret |
| Exness | 2 | ✅ Active | JWT token |

---

## Continuous Integration

For CI/CD environments, you can:

1. **Skip integration tests** (fast, only unit tests):
   ```bash
   python -m pytest tests/ -v -m "not integration"
   ```

2. **Run only mock tests** (no credentials needed):
   ```bash
   python -m pytest tests/ -v -k "mock"
   ```

3. **Run with encrypted secrets** (GitHub Actions example):
   ```yaml
   - name: Run integration tests
     env:
       OSTIUM_PRIVATE_KEY: ${{ secrets.OSTIUM_PRIVATE_KEY }}
       BYBIT_API_KEY: ${{ secrets.BYBIT_API_KEY }}
       BYBIT_API_SECRET: ${{ secrets.BYBIT_API_SECRET }}
     run: python -m pytest tests/test_integration.py -v
   ```

---

## Troubleshooting

### "Skipped" Tests
Tests are skipped when credentials are not set. This is expected behavior.

### Connection Errors
- **Ostium**: Check RPC URL and private key format (with 0x prefix)
- **Bybit**: Ensure testnet account is funded with test USDT
- **Exness**: Token expires after ~24 hours, needs refresh

### Rate Limiting
Integration tests make real API calls. Don't run them in tight loops.

---

## Adding New Integration Tests

Template for new exchange integration tests:

```python
class TestNewExchangeIntegration:
    @pytest.mark.integration
    def test_new_exchange_initialization(self, has_newexchange_credentials):
        if not has_newexchange_credentials:
            pytest.skip("NEWEXCHANGE credentials not set")
        
        from trading_bot.exchange.newexchange import create_newexchange
        
        exchange = create_newexchange(...)
        assert exchange is not None
        assert exchange.connected is True
```

Add credentials fixture to `conftest.py`:

```python
@pytest.fixture(scope="session")
def has_newexchange_credentials():
    return bool(os.getenv('NEWEXCHANGE_API_KEY'))
```
