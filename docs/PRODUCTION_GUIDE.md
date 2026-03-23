# Production Guide — HFT Trading Bot

## Quick Start

```bash
# Paper trade with best AI preset (H1, safest)
python3 -m trading_bot.interface.cli \
  --strategy ai_best \
  --mode paper \
  --symbol XAUUSDm \
  --balance 10000 \
  --leverage 200

# Paper trade with best SMC scalper (M15, scalping)
python3 -m trading_bot.interface.cli \
  --strategy smc_best \
  --mode paper \
  --symbol XAUUSDm \
  --balance 10000 \
  --leverage 200

# With Telegram alerts
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python3 -m trading_bot.interface.cli --strategy ai_best --mode paper
```

---

## Strategy Presets (Backtested)

### ✅ `ai_best` — Primary Production Preset
- **Timeframe:** H1 (1-hour bars)
- **Backtest (3mo XAUUSD H1):** +6–12% return, 33 trades, WR ~51%, PF 1.09–1.18, Sharpe 0.6–1.2, Max DD ~21%
- **Risk profile:** Medium — moderate drawdown, swing-style holds (hours to days)
- **Best for:** Reliable steady gains, not for "profit today"
- **Params:** `confidence=0.55, SL=3.0x ATR, TP=4.0x ATR, retrain=20 bars`

### ✅ `smc_best` — Best Scalping Preset  
- **Timeframe:** M15 (15-minute bars)
- **Backtest (2mo XAUUSD M15):** +4.1% return, 13 trades, WR 53.8%, PF 1.42, **Sharpe 2.44**, Max DD **6.2%**
- **Risk profile:** Low DD, but fewer trades — only ~13 trades in 2 months
- **Best for:** Scalping with low drawdown, best Sharpe ratio
- **Strategy:** Smart Money Concepts — Order Blocks, Fair Value Gaps, Break of Structure
- **Params:** `SL=1.5x ATR, TP=3.0x ATR, OB strength=0.2`

### 🧪 `ai_scalp_aggressive` — Experimental M15
- **Timeframe:** M15
- **Status:** EXPERIMENTAL — not profitable yet in backtests (AI needs more data on M15)
- **Use only on paper** until model has accumulated 1–2 months of live training
- **Params:** `confidence=0.45, SL=1.5x ATR, TP=2.5x ATR, lookahead=5 bars`

### 🧪 `ai_scalp_safe` — Experimental M15
- **Timeframe:** M15
- **Status:** EXPERIMENTAL — safer version of ai_scalp_aggressive
- **Params:** `confidence=0.55, SL=2.0x ATR, TP=3.0x ATR, lots=0.03`

### 📉 `ai_conservative` — Low-Risk H1
- **Timeframe:** H1
- **Best for:** Very small accounts or high risk-aversion
- **Params:** `confidence=0.60, lots=0.02, max_positions=1`

---

## Strategy Comparison Table

| Preset             | TF  | Return (backtest) | Trades | WR    | PF   | Sharpe | Max DD | Status     |
|--------------------|-----|-------------------|--------|-------|------|--------|--------|------------|
| `ai_best`          | H1  | +6–12% / 3mo      | 33     | 51.5% | 1.09 | 0.61   | 21.1%  | ✅ PROD    |
| `smc_best`         | M15 | +4.1% / 2mo       | 13     | 53.8% | 1.42 | 2.44   | 6.2%   | ✅ PROD    |
| `ai_conservative`  | H1  | ~+4% / 3mo        | ~20    | ~50%  | ~1.0 | ~0.3   | ~15%   | ✅ PROD    |
| `ai_scalp_aggressive` | M15 | ❌ LOSS         | 153    | 37%   | 0.71 | -2.2   | 37.7%  | 🧪 PAPER  |
| `ai_scalp_safe`    | M15 | ❌ LOSS           | ~100   | ~38%  | 0.72 | -2.0   | ~35%   | 🧪 PAPER  |
| `mean_reversion`   | M15 | ❌ LOSS           | 1055   | 37.9% | 0.20 | -      | 739%   | ❌ BROKEN |
| `regime_scalper`   | M15 | ❌ LOSS           | 459    | 34%   | 0.52 | -      | 201%   | ❌ BROKEN |

---

## Research Summary (March 2026)

### Key findings from GitHub/arXiv research:
1. **xaubot-ai** (GifariKemal): XGBoost + SMC + HMM regime → 63.9% WR, PF 2.64, DD 2.2% on M15  
   → SMCScalperStrategy is inspired by this architecture
2. **EA_SCALPER_XAUUSD** (francomascareloai): SMC + ML regime, prop-firm style
3. **Mean Reversion**: In theory works on short TF, but XAU volatility kills naive mean reversion
4. **AI on H1**: Works! On M15 the AI doesn't have enough training horizon per bar to converge.

### Why AI underperforms on M15 vs H1:
- M15 `lookahead_bars=5` = 75 min prediction horizon
- Very noisy at 15-min level; model sees patterns that don't persist
- Solution: either use **more data** (6+ months M15) or **longer lookahead** (but then it's not scalping)
- H1 `lookahead_bars=10` = 10 hours; cleaner signal

### Why SMC works better for scalping:
- Order Blocks are institutional price levels — real supply/demand zones
- BOS (Break of Structure) confirms direction before entry
- Tight ATR SL (1.5x) with wide ATR TP (3.0x) = RR 2:1
- Only 13 trades / 2 months = very selective, high quality entries

---

## Recommended Operating Mode

### For fast profit (scalping focus):
1. Run `smc_best` on M15 paper first — verify behavior
2. If DD stays below 10% over 2 weeks, go live with 0.01 lots
3. Scale up gradually

### For steady consistent profit:
1. Run `ai_best` on H1 paper for 2 weeks
2. Target: 5–10% per month, max 25% DD
3. Use `ai_conservative` if account size < $500

### Combined approach (recommended):
```bash
# Terminal 1: H1 AI (backbone)
python3 -m trading_bot.interface.cli --strategy ai_best --mode paper

# Terminal 2: M15 SMC scalper
python3 -m trading_bot.interface.cli --strategy smc_best --mode paper
```

---

## Environment Variables

```bash
# Telegram alerts (optional but strongly recommended)
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="your_chat_id"

# Broker (choose one)
export OSTIUM_PRIVATE_KEY="0x..."   # Ostium DEX
export EXNESS_ACCOUNT_ID="12345"    # Exness
export EXNESS_TOKEN="your_token"
export BYBIT_API_KEY="..."          # Bybit
export BYBIT_API_SECRET="..."
```

---

## Risk Management (auto-applied)

All presets automatically use:
- **RiskManager**: daily loss limit, drawdown halt, loss streak detection
- **CircuitBreaker**: halts if exchange API fails repeatedly  
- **ValidatorChain**: price sanity, balance, position count, lot size
- **AuditLogger**: full trade trail → `logs/audit_YYYY-MM-DD.jsonl`
- **StateManager**: auto-saves state every 30s → `data/state.json` (crash recovery)
- **TelegramNotifier**: sends trade open/close/risk alerts

Default risk limits:
- Max daily loss: configurable (default unlimited, set in config)
- Max drawdown: 20% (circuit breaker triggers)
- Max consecutive losses: 5 (circuit breaker triggers)
- Rapid losses: 3 losses in 30 min (circuit breaker triggers)

---

## Commits History (key milestones)
- `65d618a` — wire audit+validators+state, fix update_pnl crash
- `6464f5f` — production AI preset + Telegram + risk management
- `a8e0198` — backtest engine fix + strategy sweep
- `e1affe0` — loss streak manager + unified risk gateway
- `2687971` — 3-month backtest runner
- `86f4f22` — Telegram notifier
- `bd11b8a` — MACD fix

*Last updated: 2026-03-23*
