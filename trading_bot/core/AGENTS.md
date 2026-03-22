# Core Module

Core abstractions, data models, and backtest engine.

## Structure

```
trading_bot/core/
├── models.py            # Data models (Order, Position, Trade, Balance)
├── interfaces.py        # Exchange/Strategy interface definitions
├── backtest_engine.py  # MT5-style strategy tester (492 lines)
├── backtest_runner.py  # Multi-provider backtest framework (525 lines)
├── hft_optimizer.py    # HFT parameter grid search
└── strategy_runner.py  # Live trading runner (328 lines)
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Data models | `models.py` | Order, Position, Trade, Balance dataclasses |
| Add interface | `interfaces.py` | Abstract base class definitions |
| Backtesting | `backtest_engine.py` | Bar-by-bar simulation |
| Multi-provider tests | `backtest_runner.py` | Compare strategies across providers |
| HFT tuning | `hft_optimizer.py` | Grid search optimizer |

## Data Models

Key dataclasses in `models.py`:
- `Position`: id, symbol, side, entry_price, amount, unrealized_pnl, sl, tp
- `Order`: symbol, side, amount, price, type
- `Trade`: entry/exit times, pnl, duration
- `Balance`: total, used, free

## Backtest Engine

```python
engine = BacktestEngine(
    initial_balance=10000,
    leverage=200,
    spread=0.02,      # XAU/USD spread
    commission=0,     # Per lot
    slippage=0.01     # Price slippage
)

result = engine.run(strategy, data, symbol="XAUUSD")
# Returns BacktestResult with metrics
```

## Conventions

- **Dataclasses**: All models use `@dataclass` with type hints
- **Immutability**: Treat models as immutable (create new, don't modify)
- **Units**: Prices in quote currency, amounts in lots
- **Timestamps**: Milliseconds (UNIX epoch * 1000)

## Anti-Patterns

- **Don't** use pandas inside strategy `on_tick()` (slow)
- **Don't** modify backtest engine state directly
- **Never** use real exchange connections in backtests
- **Don't** ignore slippage in backtests (unrealistic results)

## Testing

Run integration tests: `python -m pytest tests/test_integration.py -v`
