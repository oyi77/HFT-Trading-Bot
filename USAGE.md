# 📘 Trading Bot Usage Guide

## 🖥️ Interface Modes

The bot has **three distinct interface modes**:

| Interface | Command | Description |
|-----------|---------|-------------|
| **CLI** | `-i cli` | Command line only - use arguments |
| **TUI** | `-i tui` | Terminal UI with interactive wizard (default) |
| **WEB** | `-i web` | Web interface (coming soon) |

---

## 🚀 Quick Start

### TUI Mode (Default) - Interactive Wizard
```bash
# Start with interactive setup wizard (recommended)
python trading_bot.py
# or explicitly:
python trading_bot.py -i tui
```

The wizard guides you through:
1. 📋 Select Trading Mode (Paper/Frontest/Real)
2. 🏦 Select Provider (Exness/CCXT)
3. 🔐 Configure Authentication (if needed)
4. ⚙️ Set Trading Parameters (Symbol, Lot, SL, TP)
5. 📊 Review Configuration
6. 🚀 Start Trading

### CLI Mode - Arguments Only
```bash
# Show config and ask confirmation
python trading_bot.py -i cli --mode paper --symbol XAUUSDm --lot 0.02

# Auto-start without confirmation
python trading_bot.py -i cli -y --mode paper --lot 0.02

# All available params
python trading_bot.py -i cli \
    --mode paper \
    --symbol XAUUSDm \
    --lot 0.01 \
    --sl 500 \
    --tp 1000 \
    --balance 1000
```

### Web Mode
```bash
# Launch web interface
python trading_bot.py -i web
```

---

## 📋 Command Line Options

```
python trading_bot.py [OPTIONS]

Options:
  -i, --interface {cli,tui,web}  Interface type (default: tui)
  -y, --yes                      Auto-start without confirmation (CLI only)
  
  --mode {paper,frontest,real}   Trading mode
  --symbol SYMBOL                Trading symbol (default: XAUUSDm)
  --lot LOT                      Lot size (default: 0.01)
  --leverage LEVERAGE            Leverage (default: 2000)
  --sl SL                        Stop loss in pips (default: 500)
  --tp TP                        Take profit in pips (default: 1000)
  --balance BALANCE              Initial balance (default: 100)
  --provider {exness,ccxt}       Exchange provider
  --strategy STRATEGY            Trading strategy
  
  -h, --help                     Show help
```

---

## 💡 Usage Examples

### Paper Trading (TUI Wizard)
```bash
# Use the interactive wizard to configure
python trading_bot.py -i tui
```

### Paper Trading (CLI)
```bash
# Quick paper trading test
python trading_bot.py -i cli -y

# With custom parameters
python trading_bot.py -i cli \
    --symbol EURUSD \
    --lot 0.02 \
    --balance 500 \
    -y
```

### Frontest Mode (Demo Account)
```bash
# Using TUI wizard (enter credentials interactively)
python trading_bot.py -i tui

# Using CLI with env vars
export EXNESS_TOKEN="your_jwt_token"
python trading_bot.py -i cli \
    --mode frontest \
    --provider exness \
    -y
```

### Real Trading ⚠️
```bash
# ⚠️ REAL MONEY AT RISK!
# Recommended: Use TUI wizard to double-check settings
python trading_bot.py -i tui
```

---

## 🎮 TUI Controls (Dashboard)

When running TUI mode, use these keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Q` | Quit the bot |
| `S` | Stop trading and show final stats |
| `P` | Pause trading |
| `R` | Resume trading |

---

## 🎯 Trading Modes

| Mode | Account | Real Data | Real Money | When to Use |
|------|---------|-----------|------------|-------------|
| 📘 **PAPER** | ❌ Not needed | ❌ Simulated | ❌ Virtual | Testing strategies |
| 📗 **FRONTEST** | ✅ Demo | ✅ Real | ❌ No risk | Test with real data |
| 📕 **REAL** | ✅ Real | ✅ Real | ⚠️ **YES** | Live trading |

---

## 🔧 Architecture

```
trading_bot/
├── interface/
│   ├── cli.py            # CLIInterface - args only
│   ├── tui.py            # TUIInterface - interactive wizard + dashboard
│   ├── web.py            # WebInterface - web UI
│   └── setup_wizard.py   # Interactive setup wizard (used by TUI)
├── trading_engine.py     # Core trading logic
└── ...
```

Each interface:
- **CLI**: Uses command-line arguments, minimal interaction
- **TUI**: Rich dashboard with interactive wizard
- **Web**: Browser-based interface (coming soon)

---

## 📋 Provider Authentication

### Exness
```bash
export EXNESS_TOKEN="your_jwt_token"
export EXNESS_ACCOUNT_ID="413461571"
export EXNESS_SERVER="trial6"
```

### CCXT (Binance, Bybit, etc.)
```bash
export EXCHANGE_NAME="binance"
export EXCHANGE_API_KEY="your_api_key"
export EXCHANGE_API_SECRET="your_secret"
```
