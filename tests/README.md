# 🧪 Trading Bot Test Suite

## Overview

Comprehensive test suite covering authentication, exchanges, strategies, and end-to-end workflows.

## Test Structure

```
tests/
├── __init__.py           # Test package
├── conftest.py           # Pytest configuration and fixtures
├── test_auth.py          # Authentication tests (12 tests)
├── test_exchange.py      # Exchange provider tests (28 tests)
├── test_strategy.py      # Strategy tests (18 tests)
├── test_config.py        # Configuration tests (12 tests)
├── test_integration.py   # End-to-end tests (15 tests)
└── README.md            # This file
```

## Running Tests

### Run All Tests
```bash
python run_tests.py
# or
python -m pytest tests/ -v
```

### Run Quick Tests Only (Unit tests)
```bash
python run_tests.py --quick
```

### Run With Coverage
```bash
python run_tests.py --coverage
# Requires: pip install pytest-cov
```

### Run Specific Test File
```bash
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_strategy.py -v
```

### Run Specific Test
```bash
python -m pytest tests/test_auth.py::TestAuthManager::test_authenticate_exness_from_env -v
```

## Test Categories

### Unit Tests (Fast)
- `test_auth.py` - Credential handling, auth manager
- `test_exchange.py` - Provider initialization, API methods
- `test_strategy.py` - Strategy logic, signal generation
- `test_config.py` - Config serialization, validation

### Integration Tests (Comprehensive)
- `test_integration.py` - End-to-end workflows, multi-provider support

## Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Auth | 12 | ✅ Credentials, Env vars, Multiple providers |
| Exchange | 28 | ✅ Exness API, Simulator, Interface compliance |
| Strategy | 18 | ✅ Config, Session filter, Trailing stops |
| Config | 12 | ✅ Serialization, Validation |
| Integration | 15 | ✅ E2E flow, Safety checks |
| **Total** | **85** | **✅ All Passing** |

## Key Test Scenarios

### Authentication
- ✅ Environment variable loading
- ✅ Manual credential input
- ✅ Token masking/unmasking
- ✅ Multiple provider support (Exness, CCXT, Ostium)

### Exchange Operations
- ✅ Connection establishment
- ✅ Balance/equity queries
- ✅ Position open/close/modify
- ✅ SL/TP trigger simulation
- ✅ Price updates

### Strategy Logic
- ✅ Signal generation (open/hedge/pending)
- ✅ Session detection (Asia/London/NY)
- ✅ Trailing stop calculation
- ✅ Break-even logic

### Safety & Validation
- ✅ Lot size warnings
- ✅ Leverage checks
- ✅ Real mode confirmations
- ✅ Account type validation

## Adding New Tests

```python
# tests/test_feature.py
import pytest
from trading_bot.module import Feature

class TestFeature:
    def test_feature_does_something(self):
        feature = Feature()
        result = feature.do_something()
        assert result == expected
```

## Continuous Integration

Tests can be run in CI/CD:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install pytest
    python -m pytest tests/ -v --tb=short
```

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the project root
cd /Users/paijo/riset-trading
python -m pytest tests/ -v
```

### Missing Dependencies
```bash
pip install pytest pytest-cov
```

### Test Failures
Run with more detail:
```bash
python -m pytest tests/ -vv --tb=long
```
