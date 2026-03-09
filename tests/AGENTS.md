# Tests

Test suite with pytest markers and fixtures.

## Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_auth.py         # Authentication (12 tests)
├── test_exchange.py     # Exchange providers (28 tests)
├── test_strategy.py     # Strategies (18 tests)
├── test_config.py       # Configuration (12 tests)
├── test_integration.py  # Integration (703 lines, 15 tests)
├── test_robustness.py   # Error handling (527 lines)
├── test_exness_metrics.py
├── test_frontest_pnl_live.py
├── test_pnl_key_fix.py
└── __init__.py
```

## Test Markers

```python
@pytest.mark.unit          # Fast, no external deps
@pytest.mark.integration   # May use external services
@pytest.mark.slow          # Long-running tests
@pytest.mark.network       # Requires network access
```

## Run Tests

```bash
# All tests
python run_tests.py

# Quick only
python run_tests.py --quick  # Excludes slow + integration

# Specific file
python -m pytest tests/test_exchange.py -v

# With coverage
python run_tests.py --coverage
```

## Fixtures (conftest.py)

```python
@pytest.fixture
def mock_exchange():
    return MockExchange()

@pytest.fixture
def sample_config():
    return XAUHedgingConfig(lots=0.01)
```

## Conventions

- **Test Names**: `test_<component>_<behavior>()`
- **Mocking**: Use `unittest.mock` for exchange calls
- **Assertions**: Use pytest style (`assert x == y`)
- **Parametrize**: Use `@pytest.mark.parametrize` for multiple cases

## Anti-Patterns

- **Never** use real API keys in tests
- **Don't** make real trades in tests
- **Don't** depend on external services for unit tests
- **Never** hardcode paths in tests (use `tmp_path` fixture)

## Large Test Files

- `test_integration.py` (703 lines): End-to-end workflows
- `test_robustness.py` (527 lines): Error scenarios, edge cases
- `test_exchange.py` (340 lines): Exchange provider tests
- `test_strategy.py` (314 lines): Strategy logic tests

## Testing Patterns

```python
# Mock exchange
def test_strategy_signal(mock_exchange):
    strategy = XAUHedgingStrategy()
    action = strategy.on_tick(2650.0, 2649.5, 2650.5, [])
    assert action['action'] == 'open'
```
