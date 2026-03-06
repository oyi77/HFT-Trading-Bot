# 📊 Strategy Comparison: ahdu.mq5 vs halah.mq5

## 🎯 Executive Summary

| Aspek | ahdu.mq5 (v2.10) | halah.mq5 (v3.00) |
|-------|------------------|-------------------|
| **Versi** | Basic | Enhanced |
| **Session Filter** | ❌ Tidak ada | ✅ London/NY only |
| **Auto Lot** | ❌ Fixed | ✅ Risk-based |
| **7-Day Return (H1)** | **+406.09%** 🥇 | +253.58% |
| **Win Rate (H1)** | 50.0% | 48.5% |
| **Profit Factor (H1)** | **4.12** 🥇 | 3.90 |

**Winner untuk periode 7 hari: ahdu.mq5 (Basic)** - Session filter malah mengurangi profit!

---

## 📋 Detail Perbandingan

### Strategi v1: ahdu.mq5 (Basic Hedging)
```c
// Parameter utama
Lots = 0.10;
StopLoss = 1500;
Trailing = 500;
TrailStart = 1000;
XDistance = 300;

// Risk Management
UseDailyLossLimit = true;
MaxDailyLoss = 100.0;
UseMaxDrawdown = true;
MaxDrawdownPercent = 20.0;

// Break Even
UseBreakEven = true;
BreakEvenProfit = 500;
BreakEvenOffset = 10;

// ❌ NO Session Filter
```

**Logic:**
1. Buka posisi utama (BUY/SELL alternate)
2. Pasang SL 1500 points
3. Jika profit 500 points → Break even (pindah SL ke entry + 10)
4. Jika profit 1000+ points → Trailing stop aktif
5. Buat pending order (hedge) di SL + XDistance
6. **Trade 24/5 (semua session)**

---

### Strategi v2: halah.mq5 (Session Filter)
```c
// Parameter tambahan
UseAutoLot = true;
RiskPercent = 1.0;

// ✅ Session Filter
UseAsiaSession = true;      // 00:00-07:00 GMT
UseLondonOpen = true;       // 07:00-12:00 GMT
UseLondonPeak = true;       // 12:00-17:00 GMT
UseNYSession = true;        // 17:00-22:00 GMT

// Auto Detect
Auto-detect digit, pair, cent account
```

**Logic:**
1. Sama seperti v1 untuk hedging & risk management
2. **TAPI**: Hanya trade di London Open, London Peak, NY
3. **SKIP**: Asia session (00:00-07:00 GMT) dan Off-Market (22:00-24:00)
4. Auto lot sizing berdasarkan equity

---

## 📊 Backtest Results (7 Days: Feb 26 - Mar 5, 2026)

### H1 (1 Hour) - Best Performer

| Metric | v1 ahdu (Basic) | v2 halah (Session) | Difference |
|--------|-----------------|-------------------|------------|
| **Return** | **+406.09%** 🥇 | +253.58% | +152.51% |
| Final Balance | **$506.09** | $353.58 | +$152.51 |
| Total Trades | 106 | 68 | -38 |
| Win Rate | **50.0%** | 48.5% | +1.5% |
| Profit Factor | **4.12** | 3.90 | +0.22 |
| Max Drawdown | $60.16 | $60.16 | Same |
| Skipped Trades | 0 | 39 Asia/Off | - |

### All Timeframes Summary

| TF | v1 Return | v2 Return | Winner | Skipped (v2) |
|----|-----------|-----------|--------|--------------|
| M1 | -733.14% | -475.62% | v2* | 602 Asia |
| M5 | -188.83% | -152.14% | v2* | 277 Asia |
| M15 | **+219.94%** | +121.35% | **v1** | 124 Asia |
| M30 | **+249.77%** | +158.66% | **v1** | 69 Asia |
| H1 | **+406.09%** | +253.58% | **v1** | 39 Asia |

*Note: v2 menang di M1/M5 tapi keduanya loss besar (tidak recommended)

---

## 🔍 Analysis: Kenapa Session Filter Malah Kurang Profit?

### 1. Asia Session Ternyata Profitable
```
Periode: Feb 26 - Mar 5, 2026

v1 (Trade All): +406% (H1)
v2 (Skip Asia): +253% (H1)

Kesimpulan: Di periode 7 hari ini, Asia session memberikan
kontribusi positif +152% return!
```

### 2. Market Condition Specific
```
Karakteristik periode test:
• Gold trending bullish ($5,120 → $5,595)
• Volatilitas tinggi di SEMUA session
• Asia session bukan "choppy" seperti biasanya

Result: Skip Asia = skip profit opportunity
```

### 3. Trade Frequency Impact
```
v1 H1: 106 trades (15 trades/day)
v2 H1: 68 trades (10 trades/day)

Dengan win rate 50%, less trades = less profit
```

---

## 🎯 Kapan Session Filter Berguna?

### Session Filter HELPS ketika:
1. ✅ **Asia session choppy/ranging** (tidak trending)
2. ✅ **Low volatility period** (news impact minimal)
3. ✅ **Long-term trading** (filter noise harian)
4. ✅ **Risk management** (kurangi over-trading)

### Session Filter HURTS ketika:
1. ❌ **Strong trend di semua session** (kehilangan opportunity)
2. ✅ **High volatility 24/5** (gold trending)
3. ✅ **Short-term trading** (perlu frequency)

---

## 💡 Recommendation

### Untuk Periode 7 Hari Ini:
```
🏆 WINNER: v1 ahdu.mq5 (Basic)
• Return: +406% vs +253%
• Lebih banyak trade opportunity
• Asia session profitable
```

### Untuk Live Trading Umum:
```
🎯 RECOMMENDED: v2 halah.mq5 (Session Filter)
• Lebih aman untuk long-term
• Hindari Asia choppy hours
• Auto lot sizing
• Better risk management

⚠️ TAPI: Jika market trending kuat, pertimbangkan
        disable session filter untuk maximize profit
```

### Hybrid Approach:
```python
# Dynamic session filter
if volatility_high:
    trade_all_sessions = True  # Maximize profit
else:
    trade_all_sessions = False  # Filter noise
```

---

## 📁 File Backtest

```
data/
├── exness_7d_m1.csv   (6,873 candles / 7 days)
├── exness_7d_m5.csv   (1,379 candles / 7 days)
├── exness_7d_m15.csv  (459 candles / 7 days)
├── exness_7d_m30.csv  (229 candles / 7 days)
└── exness_7d_h1.csv   (114 candles / 7 days)

Strategy: Hedging + Break Even + Trailing Stop
Period: Feb 26 - Mar 5, 2026 (7 days)
Capital: $100
Lot Size: 0.005
```

---

## 🔬 Next Steps

### 1. Test Lebih Lama
```
Butuh data >3 bulan untuk kesimpulan lebih akurat
7 hari terlalu singkat untuk judge session filter
```

### 2. Optimize Session Filter
```
Coba variasi:
• Asia ON/OFF
• London only
• NY only
• London+NY (current)

Cari kombinasi terbaik untuk pair XAU/USD
```

### 3. Volatility-Based Filter
```
Gunakan ATR atau indikator volatility:
• High volatility → Trade all sessions
• Low volatility → Skip Asia
```

---

## 📝 Conclusion

| Skenario | Recommended |
|----------|-------------|
| **Trending Market** | v1 ahdu (no filter) |
| **Ranging Market** | v2 halah (session filter) |
| **Unknown** | v2 halah (safer) |
| **Max Profit** | v1 ahdu (higher frequency) |
| **Min Risk** | v2 halah (less trades) |

**Bottom Line:**
- Session filter adalah **safety feature**, bukan profit maximizer
- Di periode 7 hari ini, Asia session **kebetulan profitable**
- Untuk live trading aman: pakai v2 halah dengan session filter
- Jika yakin trending kuat: boleh coba v1 ahdu tanpa filter

---

*Generated: 2026-03-05*
*Data: Exness XAUUSDm Real Spot Prices*
*Period: 7 days (Feb 26 - Mar 5, 2026)*
