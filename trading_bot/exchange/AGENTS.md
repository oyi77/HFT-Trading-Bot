# Exchange Module

Exchange provider implementations for multiple trading platforms.

## Structure

```
trading_bot/exchange/
├── base.py              # Abstract Exchange interface
├── simulator.py         # Paper trading simulator
├── paper_trading.py     # Paper trading wrapper
├── ccxt.py             # CCXT integration wrapper
├── exness_web.py       # Exness Web API client (665 lines, rate-limited)
├── exness_exchange.py  # Exness MT5 wrapper
├── ostium.py           # Ostium DEX integration (842 lines)
├── bybit_exchange.py   # Bybit native API (403 lines)
└── websocket_client.py # WebSocket base
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Add new exchange | `base.py` → new file | Inherit from `Exchange` ABC |
| Rate limiting | `exness_web.py` | Uses retry_with_backoff decorator |
| DEX integration | `ostium.py` | Blockchain-specific patterns |
| WebSocket feeds | `websocket_client.py` | Base class for real-time data |

## Conventions

- **Abstract Base Class**: All exchanges inherit from `Exchange` in `base.py`
- **Factory Function**: Use `create_*_provider()` functions for instantiation
- **Rate Limiting**: Implement `retry_with_backoff` for API-heavy providers
- **Caching**: Use `_cache` dict with TTL for frequently accessed data (balance, positions)
- **Point Values**: XAU/USD uses 0.01, forex uses 0.0001

## Anti-Patterns

- **Never** hardcode API tokens in exchange files
- **Never** bypass rate limiting (causes 429 bans)
- **Don't** use blocking calls in async contexts
- **Don't** cache position data without invalidation logic

## Unique Styles

### Retry Decorator Pattern
```python
@retry_with_backoff(max_retries=3, backoff_factor=1.0)
def api_call(self):
    # Auto-retries on 429, 503, 502
```

### Provider Config Pattern
```python
def create_exchange_provider(account_id: int, token: str) -> Exchange:
    config = ExchangeConfig(...)
    return ExchangeProvider(config)
```

## Large Files

- `ostium.py` (842 lines): DEX complexity - blockchain interaction, gas handling
- `exness_web.py` (665 lines): Rate limiting, caching, retry logic
- `bybit_exchange.py` (403 lines): Native API implementation

## Testing

Run exchange tests: `python -m pytest tests/test_exchange.py -v`
