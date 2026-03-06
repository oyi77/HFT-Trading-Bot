# Trading Bot - Agent Guide

## Project Overview

This is a **Modular Trading Bot** written in Python that supports automated trading across multiple exchanges. The bot implements hedging strategies ported from MQL5 Expert Advisors (ahdu.mq5 and halah.mq5) with both simulation and live trading capabilities.

### Key Capabilities
- **Three Trading Modes**: Paper (simulation), Frontest (demo account), Real (live trading)
- **Multiple Interfaces**: CLI (command line), TUI (Rich-based terminal UI), Web (optional)
- **Multi-Provider Support**: Exness (Forex/CFDs), CCXT-based exchanges (Binance, Bybit, etc.)
- **Strategy Support**: XAU Hedging, Grid, Trend Following with session awareness
- **Risk Management**: Daily loss limits, max drawdown, lot size validation, break-even

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Exchange Integration | ccxt>=4.0.0 |
| Numerical Computing | numpy>=1.24.0 |
| Environment Config | python-dotenv>=1.0.0 |
| Terminal UI | rich (for TUI mode) |
| Testing | pytest |

---

## Project Structure

```
.
├── trading_bot.py              # Main entry point (primary CLI)
├── main.py                     # Alternative entry point (legacy)
├── trading_bot_tui.py          # Standalone TUI version
├── run_tests.py                # Test runner script
├── requirements.txt            # Python dependencies
├── pytest.ini                 # Pytest configuration
├── config.example.env         # Example environment config
│
├── trading_bot/               # Main package
│   ├── __init__.py
│   ├── bot.py                 # Core bot implementation
│   ├── trading_engine.py      # Trading engine (interface-agnostic)
│   │
│   ├── core/                  # Core abstractions
│   │   ├── models.py          # Data models (Order, Position, Trade, etc.)
│   │   ├── interfaces.py      # Exchange interface definitions
│   │   ├── backtest_engine.py
│   │   └── strategy_runner.py
│   │
│   ├── exchange/              # Exchange providers
│   │   ├── base.py            # Abstract Exchange class
│   │   ├── simulator.py       # Paper trading simulator
│   │   ├── paper_trading.py   # Paper trading wrapper
│   │   ├── ccxt.py            # CCXT integration (Binance, Bybit, etc.)
│   │   ├── exness_web.py      # Exness Web API client
│   │   ├── enhanced_exness.py
│   │   └── websocket_client.py
│   │
│   ├── interface/             # User interfaces
│   │   ├── base.py            # BaseInterface abstract class
│   │   ├── cli.py             # Command Line Interface
│   │   ├── tui.py             # Terminal UI (Rich-based)
│   │   └── web.py             # Web interface (optional)
│   │
│   ├── strategy/              # Trading strategies
│   │   ├── base.py            # Strategy abstract base class
│   │   ├── xau_hedging.py     # XAU/USD hedging strategy (main)
│   │   ├── hedging.py         # Generic hedging
│   │   ├── grid.py            # Grid trading
│   │   └── trend.py           # Trend following
│   │
│   ├── risk/                  # Risk management
│   │   └── manager.py         # RiskManager (daily loss, drawdown)
│   │
│   └── utils/                 # Utilities
│       └── auth.py            # Authentication manager
│
├── tests/                     # Test suite (85+ tests)
│   ├── conftest.py            # Pytest fixtures
│   ├── test_auth.py           # Authentication tests (12)
│   ├── test_exchange.py       # Exchange tests (28)
│   ├── test_strategy.py       # Strategy tests (18)
│   ├── test_config.py         # Config tests (12)
│   └── test_integration.py    # Integration tests (15)
│
├── docs/                      # Documentation
│   ├── ahdu.mq5               # Original MQL5 source (reference)
│   ├── halah.mq5              # Original MQL5 source (reference)
│   └── *.md                   # Various analysis docs
│
├── examples/                  # Example scripts
│   ├── complete_system_demo.py
│   ├── exness_web_example.py
│   ├── frontest_safe.py
│   └── frontest_100usd_high_risk.py
│
├── tools/                     # Utility tools
│   ├── fetch_exness_history.py
│   ├── fetch_xau_data.py
│   └── backtest_real_data.py
│
└── data/                      # Data storage
```

---

## Build and Run Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Bot

**Primary Entry Point (Recommended)**:
```bash
# TUI Mode - Interactive setup wizard (DEFAULT)
python trading_bot.py              # or: python trading_bot.py -i tui

# CLI Mode - Use arguments only
python trading_bot.py -i cli --mode paper --symbol XAUUSDm --lot 0.01

# CLI Auto-start (no confirmation)
python trading_bot.py -i cli -y --mode paper

# Frontest mode (demo account)
export EXNESS_TOKEN="your_jwt_token"
python trading_bot.py -i tui --mode frontest --provider exness
```

**Alternative Entry Point**:
```bash
python main.py --mode backtest --strategy xau --symbol XAU/USD
```

### Command Line Options
```
-i, --interface {cli,tui,web}  Interface type (default: cli)
--mode {paper,frontest,real}   Trading mode (default: paper)
--symbol SYMBOL                Trading symbol (default: XAUUSDm)
--lot LOT                      Lot size (default: 0.01)
--leverage LEVERAGE            Leverage (default: 2000)
--sl SL                        Stop loss in pips (default: 500)
--tp TP                        Take profit in pips (default: 1000)
--balance BALANCE              Initial balance (default: 100)
--provider {exness,ccxt}       Exchange provider
--strategy STRATEGY            Trading strategy (default: xau_hedging)
```

---

## Testing Instructions

### Run All Tests
```bash
python run_tests.py
# or
python -m pytest tests/ -v
```

### Run Quick Tests Only (Unit Tests)
```bash
python run_tests.py --quick
# Runs: pytest tests/ -m "not slow and not integration"
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
python -m pytest tests/test_exchange.py -v
```

### Test Markers
- `unit`: Fast unit tests (no external dependencies)
- `integration`: Integration tests (may use external services)
- `slow`: Slow tests
- `network`: Tests requiring network access

---

## Code Style Guidelines

### Architecture Patterns
1. **Abstract Base Classes**: All major components use ABC pattern
   - `Exchange` (in `exchange/base.py`)
   - `Strategy` (in `strategy/base.py`)
   - `BaseInterface` (in `interface/base.py`)

2. **Dataclasses for Models**: Data models use `@dataclass`
   - `Config`, `Order`, `Position`, `Trade`, `Balance`, `OHLCV`
   - Strategy configs like `XAUHedgingConfig`

3. **Factory Pattern**: Interface selection uses factory
   - `get_interface()` in `interface/__init__.py`

### Naming Conventions
- **Files**: snake_case.py
- **Classes**: PascalCase
- **Functions/Variables**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **Private methods**: _leading_underscore

### Code Organization
- Each module has a docstring explaining its purpose
- Type hints are used where applicable
- Abstract methods are decorated with `@abstractmethod`
- Configuration uses dataclasses with default values

---

## Configuration

### Environment Variables

**Exness Provider**:
```bash
export EXNESS_TOKEN="your_jwt_token"
export EXNESS_ACCOUNT_ID="413461571"
export EXNESS_SERVER="trial6"
```

**CCXT Provider (Binance, Bybit, etc.)**:
```bash
export EXCHANGE_NAME="binance"
export EXCHANGE_API_KEY="your_api_key"
export EXCHANGE_API_SECRET="your_api_secret"
```

**Ostium DEX**:
```bash
export OSTIUM_PRIVATE_KEY="0x..."
export OSTIUM_RPC_URL="https://arb1.arbitrum.io/rpc"
```

### Config Files
- Copy `config.example.env` to `.env` and fill in values
- Config files can be loaded from `config/` directory

---

## Security Considerations

### ⚠️ CRITICAL: Real Trading Risk
- **Real mode uses actual money** - test thoroughly in paper/frontest first
- Start with minimum lot size (0.01)
- Never risk more than you can afford to lose

### Credential Handling
- API keys and tokens should be stored in environment variables
- Never commit credentials to version control
- Use `.env` files (already in .gitignore)

### Lot Size Safety (for $100 accounts)
| Lot | Risk | Status |
|-----|------|--------|
| 0.005 | $25 (25%) | ✅ Safe |
| 0.01 | $50 (50%) | ⚠️ Max recommended |
| 0.1 | $500 (500%) | ❌ Deadly - will liquidate |

### Risk Management Features
- Daily loss limits
- Max drawdown protection
- Automatic lot size validation
- Break-even automation

---

## Key Implementation Details

### Strategy Logic (XAU Hedging)
1. Opens main position (BUY or SELL based on StartDirection)
2. Places hedge pending order at X_DISTANCE from main SL
3. Trails stop loss when profit reaches trail_start
4. Moves to break-even when profit reaches threshold
5. Maximum 2 positions (main + hedge)

### XAU/USD Specifics
- Point value: $0.01 (not 0.0001 like forex pairs)
- Session awareness: London/NY sessions are best for gold
- Smaller lot sizes recommended (gold is expensive)
- Tighter stops (gold can move fast)

### Session Times (GMT)
| Session | Time | Jakarta Time |
|---------|------|--------------|
| Asia | 00:00-07:00 | 07:00-14:00 |
| London Open | 07:00-12:00 | 14:00-19:00 |
| London Peak | 12:00-17:00 | 19:00-00:00 |
| New York | 17:00-22:00 | 00:00-05:00 |

---

## Adding New Features

### Adding a New Interface
Create a class inheriting from `BaseInterface`:
```python
from trading_bot.interface.base import BaseInterface, InterfaceConfig

class MyInterface(BaseInterface):
    def run(self):
        pass
    
    def stop(self):
        pass
    
    def log(self, message: str, level: str = 'info'):
        pass
    
    def update_metrics(self, metrics: dict):
        pass
```

### Adding a New Strategy
Create a class inheriting from `Strategy`:
```python
from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, OrderSide

class MyStrategy(Strategy):
    def on_tick(self, price, bid, ask, positions, timestamp=None):
        # Return action dict or None
        return {'action': 'open', 'side': OrderSide.BUY, 'amount': 0.1}
```

### Adding a New Exchange Provider
Create a class inheriting from `Exchange`:
```python
from trading_bot.exchange.base import Exchange

class MyExchange(Exchange):
    def connect(self) -> bool:
        pass
    
    def get_balance(self) -> Balance:
        pass
    
    def get_price(self) -> tuple:
        pass
    
    # Implement other abstract methods...
```

---

## Dependencies

From `requirements.txt`:
```
ccxt>=4.0.0       # Cryptocurrency exchange trading library
numpy>=1.24.0     # Numerical computing
python-dotenv>=1.0.0  # Environment variable management
```

Optional for TUI:
```
rich              # Terminal UI library (usually already installed)
```

Optional for coverage:
```
pytest-cov        # Coverage reporting
```

---

## Documentation Files

- `README.md` - Project overview and quick start
- `USAGE.md` - Complete usage guide with examples
- `docs/COMPLETE_SYSTEM_GUIDE.md` - Full system documentation
- `docs/STRATEGY_COMPARISON_AHDU_VS_HALAH.md` - Strategy comparison
- `docs/LEVERAGE_ANALYSIS.md` - Leverage recommendations
- `docs/EXNESS_DATA_GUIDE.md` - Exness-specific documentation
- `tests/README.md` - Testing documentation
