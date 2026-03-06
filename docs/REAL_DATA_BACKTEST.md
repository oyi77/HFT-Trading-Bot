# XAU/USD Backtesting dengan Real Data

## Ringkasan

Solusi untuk masalah data synthetic yang tidak akurat:
1. **YFinance Integration** - Download real XAU/USD historical data
2. **Exness Web Provider** - Direct API ke Exness Web Terminal
3. **Parameter Optimization** - Cari parameter terbaik dengan data real

## Cara Penggunaan

### 1. Fetch Data dari Yahoo Finance

```bash
# Fetch 1 bulan data hourly
python tools/fetch_xau_data.py --period 1mo --interval 1h --output data/xauusd_1mo.csv

# Fetch 1 tahun data daily  
python tools/fetch_xau_data.py --period 1y --interval 1d --output data/xauusd_1y.csv

# Convert ke format Exness
python tools/fetch_xau_data.py --exness-format --output data/xauusd.csv
```

### 2. Run Backtest

```bash
# Backtest dengan parameter default
python tools/backtest_real_data.py --data data/xauusd_1mo.csv

# Dengan parameter custom
python tools/backtest_real_data.py --data data/xauusd.csv --sl 500 --trail 100

# Optimization (grid search)
python tools/backtest_real_data.py --data data/xauusd.csv --optimize
```

### 3. Live Trading dengan Exness Web API

```bash
# Set environment variables
export EXNESS_ACCOUNT_ID=413461571
export EXNESS_TOKEN="eyJhbGciOiJSUzI1NiIsImtpZCI6..."
export EXNESS_SERVER="trial6"

# Run example
python examples/exness_web_example.py
```

## Hasil Optimization (Sample)

Dari testing dengan 1 bulan hourly data:

| SL   | Trail | Trades | P&L      | Return | Win Rate | Profit Factor |
|------|-------|--------|----------|--------|----------|---------------|
| 500  | 100   | 41     | +$180.76 | +1.81% | 17.1%    | 1.53          |
| 1500 | 100   | 23     | +$101.16 | +1.01% | 39.1%    | 1.24          |
| 800  | 100   | 73     | -$292.24 | -2.92% | 30.1%    | 0.64          |
| 1000 | 100   | 77     | -$515.64 | -5.16% | 32.5%    | 0.50          |

**Insight:**
- SL lebih kecil (500) lebih baik untuk data ini
- Strategy menghasilkan banyak loss kecil, few big wins (typical trend following)
- Perlu lebih banyak data untuk validasi yang kuat

## Exness Web Provider API

```python
from trading_bot.exchange.exness_web import create_exness_web_provider

# Create provider
provider = create_exness_web_provider(
    account_id=413461571,
    token="JWT_TOKEN_FROM_BROWSER",
    server="trial6"  # atau "real17" untuk real account
)

# Connect
provider.connect()

# Get data
balance = provider.get_balance()
positions = provider.get_positions("XAUUSDm")
candles = provider.get_candles("XAUUSDm", timeframe="1h", limit=100)

# Trade
ticket = provider.open_position(
    symbol="XAUUSDm",
    side="long",
    volume=0.02,
    sl=2800.0,
    tp=2900.0
)

# Modify
provider.modify_position_sl(ticket, sl=2795.0)

# Close
provider.close_position(ticket)
```

## Endpoints yang Tersedia

Berdasarkan traced data:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/accounts/{id}` | GET | Account info |
| `/v1/accounts/{id}/balance` | GET | Balance & margin |
| `/v1/accounts/{id}/positions` | GET | Open positions |
| `/v1/accounts/{id}/orders` | POST | Place order |
| `/v1/accounts/{id}/positions/{ticket}` | DELETE | Close position |
| `/v1/accounts/{id}/instruments` | GET | Available symbols |
| `/v2/accounts/{id}/instruments/{symbol}/candles` | GET | OHLCV data |

## Next Steps

1. **Download lebih banyak data** (6-12 bulan) untuk validasi yang lebih baik
2. **Test dengan different timeframes** (5m, 15m, 1h)
3. **Integrasikan dengan Exness Web Provider** untuk live trading
4. **Add session filtering** untuk trading hanya di London/NY sessions

## Perbandingan: Synthetic vs Real Data

| Aspek | Synthetic | Real (yfinance) |
|-------|-----------|-----------------|
| Volatility | Random walk | Real market structure |
| Session patterns | Tidak ada | Clear London/NY moves |
| Trend persistence | Rendah | High (gold trends well) |
| Backtest results | Break-even | Profit dengan parameter optimal |
| Confidence | Rendah | Lebih tinggi |
