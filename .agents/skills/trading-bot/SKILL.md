---
name: trading-bot
description: Advanced HFT trading bot supporting multiple exchanges and strategies.
commands:
  - name: start
    description: Start the trading bot.
    usage: python main.py [options]
  - name: backtest
    description: Run strategy backtesting.
    usage: python -c "from trading_bot.core.backtest_runner import run_strategy_comparison; run_strategy_comparison()"
  - name: optimize
    description: Run HFT optimization.
    usage: python -c "from trading_bot.core.hft_optimizer import run_hft_optimization; run_hft_optimization()"
---

# HFT Trading Bot Skill

Modular Python trading bot supporting Paper, Frontest, and Real modes with multiple strategies (XAU Hedging, Grid, Trend, HFT).

## Capabilities

- **Multi-Exchange Support**: Exness, CCXT-compatible (Binance, Bybit), and Ostium DEX.
- **Interfaces**: CLI (standard), TUI (interactive), and Web UI (monitoring).
- **Risk Management**: Mandatory safety checks for balance, equity, and lot sizing.

## Usage

### Start Trading
```bash
python main.py -i cli --mode paper --symbol XAUUSDm --lot 0.01
```

### Backtesting
Compare strategies across different providers:
```bash
python -c "from trading_bot.core.backtest_runner import run_strategy_comparison; run_strategy_comparison(providers=['all'])"
```

### Safety Rules
- Always test in **Paper** or **Frontest** mode before using **Real** money.
- Use `.env` file for API tokens; never hardcode them.
- Maximum recommended risk: 0.01 lot per $100 balance.
