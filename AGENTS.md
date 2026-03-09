# HFT Trading Bot - Agent Guide

**Generated:** 2025-03-06
**Project:** Modular Python trading bot with HFT strategy, multi-provider support

## Overview

Multi-exchange trading bot supporting Paper/Frontest/Real modes with 4 strategies:
- XAU Hedging (session-aware gold trading)
- Grid (mean reversion)
- Trend (EMA crossover)
- HFT (order book depth + volume profile)

## Architecture

```
HFT Trading Bot/
├── trading_bot.py          # Entry point (TUI/CLI)
├── trading_bot/
│   ├── exchange/          # See exchange/AGENTS.md
│   ├── strategy/          # See strategy/AGENTS.md
│   ├── core/              # See core/AGENTS.md
│   ├── interface/         # See interface/AGENTS.md
│   └── utils/
├── tests/                 # See tests/AGENTS.md
├── docs/                  # MQL5 reference, guides
├── examples/              # Usage examples
└── tools/                 # Data fetchers
```

## Quick Commands

```bash
# Run TUI (interactive)
python trading_bot.py

# Run CLI
python trading_bot.py -i cli --mode paper --symbol XAUUSDm --lot 0.01

# Run tests
python run_tests.py

# Backtest comparison
python -c "from trading_bot.core.backtest_runner import run_strategy_comparison; run_strategy_comparison(providers=['all'])"

# HFT optimization
python -c "from trading_bot.core.hft_optimizer import run_hft_optimization; run_hft_optimization()"
```

## Where to Look

| Task | Location | Sub-Guide |
|------|----------|-----------|
| Add exchange | `trading_bot/exchange/` | [exchange/AGENTS.md](trading_bot/exchange/AGENTS.md) |
| Add strategy | `trading_bot/strategy/` | [strategy/AGENTS.md](trading_bot/strategy/AGENTS.md) |
| Add UI | `trading_bot/interface/` | [interface/AGENTS.md](trading_bot/interface/AGENTS.md) |
| Backtesting | `trading_bot/core/backtest_*.py` | [core/AGENTS.md](trading_bot/core/AGENTS.md) |
| Data models | `trading_bot/core/models.py` | [core/AGENTS.md](trading_bot/core/AGENTS.md) |
| Tests | `tests/` | [tests/AGENTS.md](tests/AGENTS.md) |

## Conventions

- **ABC Pattern**: All major components use abstract base classes
- **Dataclasses**: Configs/models use `@dataclass` with type hints
- **Factory Pattern**: `get_interface()`, `create_*_provider()` functions
- **Naming**: snake_case files, PascalCase classes, UPPER_SNAKE_CASE constants

## Anti-Patterns

- **Never** commit API tokens (use `.env` files)
- **Never** use real money without testing in paper/frontest first
- **Don't** bypass rate limiting (causes IP bans)
- **Don't** use `time.sleep()` in strategy `on_tick()`
- **Don't** modify position objects directly (read-only)

## Security Rules (from codebase)

```python
# From auth.py, examples/
"Never commit tokens to git!"
"Never share your private key!"
"Never hardcode tokens in production!"
```

## Key Files

```
.
├── trading_bot.py              # Main entry point (TUI/CLI)
├── run_tests.py                # Test runner
├── requirements.txt            # Dependencies
├── config.example.env          # Env template
│
├── trading_bot/               # Main package
│   ├── bot.py                 # Core bot
│   ├── trading_engine.py      # Engine (interface-agnostic)
│   ├── exchange/              # Provider implementations
│   ├── strategy/              # Trading strategies
│   ├── core/                  # Models, backtest engine
│   ├── interface/             # CLI, TUI, Web
│   ├── risk/                  # Risk management
│   └── utils/                 # Auth, helpers
│
├── tests/                     # Test suite (114 tests)
├── docs/                      # MQL5 reference, guides
├── examples/                  # Usage examples
└── tools/                     # Data fetchers
```

## Commands

```bash
# Install
pip install -r requirements.txt

# Run TUI (default)
python trading_bot.py

# Run CLI
python trading_bot.py -i cli --mode paper --symbol XAUUSDm --lot 0.01

# Run tests
python run_tests.py              # All tests
python run_tests.py --quick      # Unit tests only
python run_tests.py --coverage   # With coverage

# Backtest all strategies
python -c "from trading_bot.core.backtest_runner import run_strategy_comparison; run_strategy_comparison(providers=['all'])"

# Optimize HFT
python -c "from trading_bot.core.hft_optimizer import run_hft_optimization; run_hft_optimization()"
```

### CLI Options
```
-i, --interface {cli,tui,web}  Interface type
--mode {paper,frontest,real}   Trading mode
--symbol SYMBOL                Trading symbol
--lot LOT                      Lot size
--leverage LEVERAGE            Leverage
--provider {exness,ccxt}       Exchange provider
--strategy STRATEGY            Strategy name
```

## Configuration

**Exness**:
```bash
export EXNESS_TOKEN="jwt_token"
export EXNESS_ACCOUNT_ID="413461571"
export EXNESS_SERVER="trial6"
```

**CCXT (Binance, Bybit)**:
```bash
export EXCHANGE_NAME="binance"
export EXCHANGE_API_KEY="..."
export EXCHANGE_API_SECRET="..."
```

**Ostium DEX**:
```bash
export OSTIUM_PRIVATE_KEY="0x..."
export OSTIUM_RPC_URL="https://arb1.arbitrum.io/rpc"
```

Copy `config.example.env` to `.env` for local config.

## Security

⚠️ **Real mode uses actual money** - test in paper/frontest first!

- Never commit tokens (use `.env`)
- Start with 0.01 lot size
- $100 account max: 0.01 lot (50% risk)

## XAU/USD Specifics

- Point value: $0.01 (not 0.0001)
- Best sessions: London Open (07-12 GMT), NY (17-22 GMT)
- Max 2 positions (main + hedge)

## Adding Features

### New Strategy
```python
from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, OrderSide

class MyStrategy(Strategy):
    def on_tick(self, price, bid, ask, positions, timestamp=None):
        return {'action': 'open', 'side': OrderSide.BUY, 'amount': 0.1}
```

### New Exchange
```python
from trading_bot.exchange.base import Exchange

class MyExchange(Exchange):
    def connect(self) -> bool: pass
    def get_balance(self) -> Balance: pass
    def get_price(self) -> tuple: pass
```

## Dependencies

```
ccxt>=4.0.0       # Exchange integration
numpy>=1.24.0     # Numerical computing
python-dotenv>=1.0.0  # Environment variables
rich              # TUI (optional)
pytest-cov        # Coverage (optional)
```

## Documentation

- `README.md` - Quick start
- `USAGE.md` - Usage guide
- `docs/` - System docs, strategy comparisons
- `tests/README.md` - Testing docs
