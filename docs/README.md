# MQL5 Source Reference

This folder contains the original MQL5 Expert Advisor source files that the Python trading bot was ported from.

## Files

### ahdu.mq5 (v2.10)
**Ahdu Bot** - Simple Hedging EA
- Main order + Hedge pending order
- Trailing stop + Break Even
- Daily loss limit + Max drawdown protection
- No session filters

### halah.mq5 (v3.00)
**Halah Bot** - Advanced Hedging EA
- All features from Ahdu Bot PLUS:
- Auto Lot based on Risk %
- Session filters (Asia/London/NY)
- More advanced risk management

## Strategy Logic

Both EAs implement a hedging strategy:

1. **Open Main Position** (BUY or SELL based on StartDirection)
2. **Place Hedge Pending Order** at X_DISTANCE from main SL
3. **Trail Stop Loss** when profit reaches trail_start
4. **Break Even** - move SL to entry + offset when profit reaches threshold
5. **Max 2 Positions** - main + hedge

## Input Parameters Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| Lots | 0.10 | Position size (if UseAutoLot=false) |
| UseAutoLot | true | Enable auto lot sizing |
| RiskPercent | 1.0 | Risk % per trade |
| StopLoss | 1500 | SL distance in points |
| TakeProfit | 0 | TP distance (0 = disabled) |
| Trailing | 500 | Trailing stop distance |
| TrailStart | 1000 | Min profit for trailing |
| XDistance | 300 | Hedge pending distance from SL |
| StartDirection | 0 | 0=BUY first, 1=SELL first |

## Session Times (Halah only)

| Session | GMT Time | Local (Jakarta) |
|---------|----------|-----------------|
| Asia | 00:00-07:00 | 07:00-14:00 |
| London Open | 07:00-12:00 | 14:00-19:00 |
| London Peak | 12:00-17:00 | 19:00-00:00 |
| New York | 17:00-22:00 | 00:00-05:00 |
| Off Market | 22:00-00:00 | 05:00-07:00 |

## Notes

- These files are for reference only
- The Python bot (`trading_bot/`) is the main implementation
- MQL5 files can be compiled in MetaTrader 5 if needed
