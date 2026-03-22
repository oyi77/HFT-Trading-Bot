# Strategy Module

Trading strategy implementations with ABC pattern.

## Structure

```
trading_bot/strategy/
├── base.py              # Strategy ABC
├── xau_hedging.py      # Gold hedging (main strategy)
├── grid.py             # Grid/mean reversion
├── trend.py            # EMA crossover trend following
├── hedging.py          # Generic hedging base
└── hft.py              # HFT with order book depth (457 lines)
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Add strategy | `base.py` → new file | Implement `on_tick()` method |
| Gold trading | `xau_hedging.py` | Session-aware, XAU/USD specific |
| Scalping | `hft.py` | Order book depth + volume profile |
| Config classes | Each strategy file | Use `@dataclass` for config |

## Conventions

- **ABC Pattern**: All strategies inherit from `Strategy` base class
- **Dataclass Config**: Each strategy has its own `*Config` dataclass
- **on_tick Method**: Core decision logic, returns action dict or None
- **Point Value**: Use `self.get_point_value(price)` for pip calculations

## Anti-Patterns

- **Never** import exchange-specific code in strategies
- **Don't** access external APIs directly from strategies
- **Don't** use `time.sleep()` in `on_tick()` (blocks engine)
- **Never** modify position objects directly (read-only)

## Strategy Pattern

```python
class MyStrategy(Strategy):
    def __init__(self, config: MyConfig):
        super().__init__(config)
        # Initialize state
    
    def on_tick(self, price, bid, ask, positions, timestamp=None):
        # Analyze market
        # Return action dict or None
        return {'action': 'open', 'side': OrderSide.BUY, 'amount': 0.01}
```

## Action Dict Formats

```python
# Open position
{'action': 'open', 'side': OrderSide.BUY, 'amount': 0.01, 'sl': 2500.0, 'tp': 2700.0}

# Close position
{'action': 'close', 'position_id': 'pos_123'}

# Pending order
{'action': 'pending', 'side': OrderSide.SELL, 'amount': 0.01, 'stop_price': 2650.0}
```

## HFT Strategy Notes

- Uses order book depth analysis (`_analyze_orderbook_depth()`)
- Volume profile with POC (Point of Control) detection
- Requires high-frequency tick data for optimal performance
- See `hft_optimizer.py` for parameter tuning

## Testing

Run strategy tests: `python -m pytest tests/test_strategy.py -v`
