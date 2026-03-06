# 🎯 Complete Trading System Guide

Sistem trading lengkap seperti MT5 dengan kemampuan:
- ✅ **Backtest** dengan data historis real
- ✅ **Paper Trading** - Simulasi dengan data real-time
- ✅ **Live Trading** - Eksekusi real via Exness Web API
- ✅ **Automation** - Bot/EA yang berjalan 24/7

---

## 📁 Arsitektur Sistem

```
trading_bot/
├── core/
│   ├── backtest_engine.py      # Engine backtest professional
│   ├── strategy_runner.py       # Automation engine (EA)
│   └── models.py               # Data models
├── exchange/
│   ├── exness_web.py           # Base Exness Web API
│   ├── enhanced_exness.py      # Extended API (orders, history)
│   ├── paper_trading.py        # Demo/paper trading provider
│   └── websocket_client.py     # Real-time data feed
├── strategy/
│   └── xau_hedging.py          # XAU/USD strategy
└── ...

tools/
├── fetch_xau_data.py           # Download data dari Yahoo
└── backtest_real_data.py       # Backtest dengan data real

examples/
└── complete_system_demo.py     # Demo lengkap semua fitur
```

---

## 🔌 Endpoint API Lengkap

### Order Management
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/v1/accounts/{id}/orders` | GET | List pending orders |
| `/v1/accounts/{id}/orders` | POST | Place market/pending order |
| `/v1/accounts/{id}/orders/{order_id}` | PATCH | Modify order |
| `/v1/accounts/{id}/orders/{order_id}` | DELETE | Cancel order |
| `/v1/accounts/{id}/orders/history` | GET | Order history |

### Position Management
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/v1/accounts/{id}/positions` | GET | Open positions |
| `/v1/accounts/{id}/positions/{ticket}` | DELETE | Close position |
| `/v1/accounts/{id}/positions/{ticket}` | PATCH | Modify SL/TP |

### Account & Market Data
| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/v1/accounts/{id}` | GET | Account info |
| `/v1/accounts/{id}/balance` | GET | Balance & margin |
| `/v1/accounts/{id}/deals` | GET | Trade history |
| `/v1/accounts/{id}/instruments` | GET | Available symbols |
| `/v2/accounts/{id}/instruments/{symbol}/candles` | GET | OHLCV data |

---

## 🔄 Workflow Sistem

### 1. Backtest Mode

```python
from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy
import pandas as pd

# Load data
df = pd.read_csv("data/xauusd.csv")

# Setup
strategy = XAUHedgingStrategy(config)
engine = BacktestEngine(initial_balance=10000, spread=0.04)

# Run
result = engine.run(strategy, df)

# Analyze
engine.print_report(result)
# Output: Win rate, Profit factor, Sharpe ratio, Drawdown, dll
```

**Fitur Backtest:**
- ✅ Tick-by-tick simulation
- ✅ Realistic spread modeling
- ✅ Slippage simulation
- ✅ Commission calculation
- ✅ Complete metrics (Sharpe, Sortino, Drawdown)
- ✅ Equity curve tracking
- ✅ Trade-by-trade analysis

### 2. Paper Trading Mode

```python
from trading_bot.exchange.paper_trading import PaperTradingProvider
from trading_bot.exchange.exness_web import create_exness_web_provider

# Setup data provider
data_provider = create_exness_web_provider(
    account_id=413461571,
    token="JWT_TOKEN",
    server="trial6"
)

# Paper trading dengan data real-time
paper = PaperTradingProvider(
    data_provider=data_provider,
    initial_balance=10000
)

# Trade seperti real, tapi virtual money
ticket = paper.open_position("XAUUSDm", "long", 0.02, sl=2800)
paper.close_position(ticket)

# Stats real-time
stats = paper.get_stats()
# Returns: win_rate, profit_factor, equity, balance, etc
```

**Fitur Paper Trading:**
- ✅ Real-time price feed dari Exness
- ✅ Virtual balance tracking
- ✅ Full position management
- ✅ SL/TP execution
- ✅ Performance metrics
- ✅ Trade history

### 3. Live Trading Mode

```python
from trading_bot.exchange.enhanced_exness import EnhancedExnessProvider

# Live provider
live = EnhancedExnessProvider(config)

# Get account info
summary = live.get_account_summary()
# Returns: balance, equity, margin, free_margin, open_positions

# Execute real trades
ticket = live.open_position(
    symbol="XAUUSDm",
    side="long", 
    volume=0.02,
    sl=price - 5,
    tp=price + 10
)

# Manage orders
live.modify_order(ticket, sl=new_sl)
live.cancel_order(ticket)

# History
orders = live.get_order_history(from_date, to_date)
deals = live.get_deals(from_date, to_date)
```

### 4. Automation Mode (EA/Bot)

```python
from trading_bot.core.strategy_runner import StrategyRunner, RunnerConfig

# Config
runner_config = RunnerConfig(
    symbol="XAUUSDm",
    enable_trading=True,
    max_positions=2,
    check_interval=1.0,  # seconds
    session_filter=True,  # Only London/NY
    max_daily_loss=100,   # Stop if lose $100/day
    max_drawdown_pct=5,   # Stop if 5% drawdown
    on_trade_open=callback_function,
    on_trade_close=callback_function,
    on_error=error_handler
)

# Create runner
runner = StrategyRunner(strategy, exchange, runner_config)

# Start automation (runs in background)
runner.start()

# Monitor
stats = runner.get_stats()

# Stop
runner.stop()
```

**Fitur Automation:**
- ✅ Real-time tick processing
- ✅ Automatic position management
- ✅ Session filtering (Asia/London/NY)
- ✅ Risk management (daily loss, drawdown limits)
- ✅ Trade notifications
- ✅ Error handling
- ✅ Performance tracking

---

## 📊 Performance Metrics

Sistem menghitung metrik lengkap seperti MT5 Strategy Tester:

### Basic Metrics
- **Total Return**: $ and %
- **Total Trades**: Jumlah trade
- **Win Rate**: % trade profitable
- **Profit Factor**: Gross Profit / Gross Loss

### Risk Metrics
- **Max Drawdown**: $ and %
- **Sharpe Ratio**: Risk-adjusted return
- **Sortino Ratio**: Downside risk only
- **Recovery Factor**: Net Profit / Max Drawdown

### Trade Metrics
- **Avg Profit/Loss**: Rata-rata win/loss
- **Largest Profit/Loss**: Extremes
- **Avg Trade Duration**: Hold time
- **Consecutive Wins/Losses**: Streaks

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Install dependencies
pip install yfinance pandas numpy requests

# Get Exness JWT token
# 1. Login ke my.exness.com
# 2. Open Web Terminal
# 3. DevTools (F12) → Network
# 4. Copy Authorization Bearer token

export EXNESS_TOKEN="eyJhbGciOiJSUzI1NiIs..."
export EXNESS_ACCOUNT_ID="413461571"
export EXNESS_SERVER="trial6"
```

### 2. Fetch Data & Backtest

```bash
# Download historical data
python tools/fetch_xau_data.py --period 1y --interval 1h

# Run backtest
python tools/backtest_real_data.py --optimize
```

### 3. Paper Trading

```bash
# Run paper trading demo
python examples/complete_system_demo.py
```

### 4. Live Trading

```bash
# ⚠️ REAL MONEY - Be careful!
export CONFIRM_LIVE=1
python examples/complete_system_demo.py
```

---

## 🔧 Advanced Features

### Multi-Symbol Trading

```python
from trading_bot.core.strategy_runner import MultiSymbolRunner

runner = MultiSymbolRunner()

# Add XAU/USD strategy
runner.add_runner("XAU", xau_runner)

# Add EUR/USD strategy  
runner.add_runner("EUR", eur_runner)

# Start all
runner.start_all()
```

### WebSocket Real-time Feed

```python
from trading_bot.exchange.websocket_client import WebSocketManager

ws = WebSocketManager()
ws.subscribe("XAUUSDm", on_tick_callback)
ws.start()

# Callback receives:
# Tick(symbol, bid, ask, last, volume, timestamp)
```

### Custom Risk Management

```python
# In StrategyRunner config
RunnerConfig(
    max_daily_loss=100,      # Max $100 loss per day
    max_drawdown_pct=5,      # Stop at 5% drawdown
    max_positions=2,         # Max 2 open positions
    check_interval=1.0       # Check every second
)
```

---

## 📝 Best Practices

### 1. Always Backtest First
```python
# Test dengan minimal 6-12 bulan data
result = engine.run(strategy, df)
if result.profit_factor < 1.5:
    print("Strategy not profitable enough")
```

### 2. Paper Trade Before Live
```python
# Run paper trading for 1-2 weeks
# Compare results dengan backtest
# Jika similar, baru ke live
```

### 3. Risk Management
```python
# Never risk more than 2% per trade
# Max 5% daily loss
# Max 10% total drawdown
```

### 4. Monitoring
```python
# Check stats regularly
stats = runner.get_stats()
if stats['win_rate'] < 30:
    print("Strategy underperforming")
```

---

## 🔗 API Reference

### ExnessWebProvider

```python
provider = create_exness_web_provider(account_id, token, server)

# Connection
provider.connect() -> bool

# Account
provider.get_balance() -> float
provider.get_equity() -> float
provider.get_margin_info() -> dict

# Trading
provider.open_position(symbol, side, volume, sl, tp) -> ticket
provider.close_position(ticket) -> bool
provider.modify_position_sl(ticket, sl, tp) -> bool
provider.get_positions(symbol) -> list

# Data
provider.get_price(symbol) -> float
provider.get_candles(symbol, timeframe, limit) -> list
```

### EnhancedExnessProvider (Extended)

```python
provider = EnhancedExnessProvider(config)

# Orders
provider.get_orders(symbol) -> list
provider.modify_order(ticket, price, sl, tp) -> bool
provider.cancel_order(ticket) -> bool
provider.get_order_history(from_date, to_date) -> list

# History
provider.get_deals(from_date, to_date) -> list
provider.get_account_summary() -> dict
```

### PaperTradingProvider

```python
paper = PaperTradingProvider(data_provider, initial_balance)

# Same interface as live provider
paper.open_position(...)
paper.close_position(...)

# Additional
paper.get_stats() -> dict
paper.check_triggers()  # Check SL/TP
paper.print_report()
```

### BacktestEngine

```python
engine = BacktestEngine(
    initial_balance=10000,
    leverage=200,
    spread=0.02,
    commission=0.5,
    slippage=0.01
)

result = engine.run(strategy, data)
engine.print_report(result)
engine.save_report(result, "report.json")
```

### StrategyRunner

```python
runner = StrategyRunner(strategy, exchange, config)

runner.start()   # Start automation
runner.stop()    # Stop
runner.print_stats()
```

---

## 🎓 Contoh Lengkap

Lihat `examples/complete_system_demo.py` untuk contoh lengkap semua mode:
1. Backtest dengan historical data
2. Paper trading dengan real-time data
3. Live trading (real money)
4. Strategy automation

---

## ⚠️ Important Notes

1. **JWT Token Security**: Never commit tokens to git!
2. **Live Trading**: Always test dengan paper trading dulu
3. **Rate Limits**: Don't poll API terlalu frequently
4. **Error Handling**: Always handle network errors gracefully
5. **Monitoring**: Check strategy performance regularly

---

Selamat trading! 🚀
