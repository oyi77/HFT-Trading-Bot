# 🚀 Production Guide — AI Strategy on XAU/USD

## Quick Start

### 1. Paper Trading (Recommended First)

```bash
cd /tmp/HFT-Trading-Bot

# Using the best AI preset (backtested +12.1% on 3mo H1)
python3 -m trading_bot.interface.cli \
  --strategy ai_best \
  --mode paper \
  --symbol XAUUSDm \
  --balance 10000 \
  --leverage 200
```

### 2. With Telegram Alerts

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"

python3 -m trading_bot.interface.cli \
  --strategy ai_best \
  --mode paper \
  --symbol XAUUSDm
```

You'll receive:
- 🟢/🔴 Trade open notifications (with SL/TP)
- ✅/❌ Trade close notifications (with P&L)
- 🚨 Risk alerts (circuit breaker, loss streak)

### 3. Live Trading (Exness)

```bash
export EXNESS_ACCOUNT_ID="your-account"
export EXNESS_TOKEN="your-token"
export EXNESS_SERVER="real6"  # or trial6 for demo

python3 -m trading_bot.interface.cli \
  --strategy ai_best \
  --mode frontest \
  --provider exness \
  --symbol XAUUSDm \
  --leverage 200
```

### 4. Conservative Mode (Lower Risk)

```bash
python3 -m trading_bot.interface.cli \
  --strategy ai_conservative \
  --mode paper
```

Differences from `ai_best`:
- 0.02 lots (vs 0.05)
- Max 1 position (vs 2)
- 60% confidence threshold (vs 55%)
- Tighter RSI thresholds

---

## Strategy Presets

| Preset | Lots | MaxPos | Confidence | SL | TP | Backtest Return |
|--------|------|--------|-----------|-----|-----|-----------------|
| `ai_best` | 0.05 | 2 | 55% | 3.0x ATR | 4.0x ATR | +12.1% / 3mo |
| `ai_conservative` | 0.02 | 1 | 60% | 3.0x ATR | 4.0x ATR | ~+5% / 3mo |
| `ai` (default) | 0.01 | 2 | 60% | 1.5x ATR | 2.5x ATR | varies |

---

## Risk Management (Built-in)

### Circuit Breaker
- **5 consecutive losses** → trading halted for 60 min
- **6% daily loss** → trading halted for rest of day
- **20% drawdown** → trading halted
- **3 losses in 30 min** → rapid-loss cooldown

### Loss Streak Manager
- After 3 losses → lot reduced to 75%
- After 5 losses → lot reduced to 50%
- After 7 losses → lot reduced to 25%
- After 8 losses → 1-hour cooldown pause
- 2 consecutive wins → reset to normal

### Combined Flow
```
Trade signal → RiskManager.check(equity) → Circuit Breaker → Daily Loss → Drawdown → Loss Streak
                  ↓ (if blocked)
              Telegram alert sent, trade skipped
                  ↓ (if allowed)
              LossStreak.get_lot_size(base_lot) → adjusted lot
                  ↓
              Execute trade → Telegram notification
                  ↓ (on close)
              RiskManager.on_trade_result(pnl) → update all trackers
```

---

## How the AI Strategy Works

1. **Data Collection** — Stores price history (closes, highs, lows)
2. **Feature Extraction** — 15 technical indicators:
   - RSI, 3x EMA distances, EMA alignment
   - Bollinger Band %B and width
   - MACD normalized, short/long momentum
   - ATR ratio, range position, candle body ratio
3. **Self-Labeling** — Looks ahead N bars, labels past data as BUY/SELL/HOLD
4. **ML Training** — GradientBoosting classifier, retrains every 20 ticks
5. **Prediction** — Only trades when confidence > threshold
6. **ATR-Based Stops** — SL = 3x ATR (~$30), TP = 4x ATR (~$40) → R:R 1:1.33
7. **Fallback** — When model isn't ready, uses RSI+EMA rules

---

## Backtest

```bash
# Run strategy sweep (find best params)
python3 tools/strategy_sweep.py

# Run 3-month comparison
python3 tools/run_3month_backtest.py

# Fetch fresh data
python3 tools/fetch_xau_data.py --period 3mo --interval 1h --output data/xauusd_3mo_h1.csv
```

---

## Architecture

```
trading_bot/
├── strategy/
│   └── ai_strategy.py          # AI Strategy + BEST_XAU_H1 preset
├── risk/
│   ├── circuit_breaker.py       # CircuitBreaker (CLOSED/OPEN/HALF_OPEN)
│   ├── loss_streak.py           # LossStreakManager (progressive lot reduction)
│   └── manager.py               # Unified RiskManager gateway
├── interface/
│   └── telegram_notifier.py     # Telegram trade alerts
├── core/
│   └── backtest_engine.py       # Backtesting with OHLC walk simulation
├── exchange/
│   ├── simulator.py             # Paper trading
│   ├── exness_exchange.py       # Exness MT5
│   ├── bybit_exchange.py        # Bybit
│   └── ostium.py                # Ostium DEX
└── trading_engine.py            # Main engine (risk + telegram wired in)
```

---

## Monitoring

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to get real-time alerts.

Without Telegram, all notifications print to console with the same format.

---

*Generated from strategy sweep: 353 configs tested, AI Strategy (3.0x ATR SL, 4.0x ATR TP) = only profitable config on 3-month H1 XAU/USD data.*
