# 📊 Exness Historical Data Guide

## Mengapa Pakai Data Exness vs yfinance?

### Perbandingan

| Aspek | Exness API | yfinance (GC=F) |
|-------|------------|-----------------|
| **Sumber** | Spot XAU/USD dari broker | Gold Futures (GC=F) |
| **Harga** | ~$2900-3000 (spot) | ~$4600-5400 (futures) |
| **Spread** | Real Exness spread | N/A |
| **Relevansi** | Sama dengan live trading | Berbeda instrument |
| **Akurasi Backtest** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Ketersediaan** | Perlu JWT token | Publik |
| **Realtime** | ✅ Yes | Delayed 15-20 menit |

### Keuntungan Data Exness

1. **Same Price Feed** - Data yang sama persis dengan yang digunakan saat live trading
2. **Real Spread** - Bid/ask spread yang realistis
3. **Spot Price** - Harga spot XAU/USD, bukan futures
4. **Session Accuracy** - Data sesuai jam trading broker
5. **Better Backtest** - Hasil backtest lebih akurat untuk strategi live

---

## 🚀 Cara Fetch Data dari Exness

### 1. CLI Tool

```bash
# Setup token
export EXNESS_TOKEN="eyJhbGciOiJSUzI1NiIs..."
export EXNESS_ACCOUNT_ID="413461571"

# Fetch 7 days of 1-hour candles
python tools/fetch_exness_history.py \
    --symbol XAUUSDm \
    --timeframe 1h \
    --days 7 \
    --output data/exness_xauusd.csv

# Fetch 1 day of 1-minute candles
python tools/fetch_exness_history.py \
    --symbol XAUUSDm \
    --timeframe 1m \
    --days 1 \
    --output data/exness_xauusd_1m.csv \
    --format backtest
```

### 2. Python Code

```python
from trading_bot.exchange.exness_web import create_exness_web_provider

# Create provider
provider = create_exness_web_provider(
    account_id=413461571,
    token="JWT_TOKEN",
    server="trial6"
)

# Fetch latest 100 1m candles
candles = provider.get_candles("XAUUSDm", timeframe="1m", limit=100)

# Fetch historical range
from datetime import datetime, timedelta
end_time = int(datetime.now().timestamp() * 1000)
start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)

historical = provider.get_historical_data(
    symbol="XAUUSDm",
    timeframe="1h",
    start_time=start_time,
    end_time=end_time
)
```

### 3. Advanced Fetcher

```python
from tools.fetch_exness_history import ExnessHistoryFetcher

fetcher = ExnessHistoryFetcher(
    account_id=413461571,
    token="JWT_TOKEN",
    server="trial6"
)

# Fetch with pagination (handles large date ranges)
df = fetcher.fetch_range(
    symbol="XAUUSDm",
    timeframe="1m",
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)

# Save for backtest
fetcher.save_to_csv(df, "data/exness_30d.csv")
```

---

## 📡 API Endpoint Detail

### Request Format

```
GET /v2/accounts/{account_id}/instruments/{symbol}/candles

Query Parameters:
- time_frame: 1, 5, 15, 30, 60, 240, 1440 (minutes)
- from: timestamp in milliseconds
- count: number of candles (-N = backwards)
- price: bid or ask
```

### Example Request

```python
import requests

url = "https://rtapi-sg.eccweb.mobi/rtapi/mt5/trial6/v2/accounts/413461571/instruments/XAUUSDm/candles"

params = {
    "time_frame": 1,          # 1 minute
    "from": 1772000759000,    # Feb 25, 2026 12:45 UTC (timestamp ms)
    "count": -968,            # 968 candles backwards
    "price": "bid"            # Bid prices
}

headers = {
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiIs..."
}

response = requests.get(url, params=params, headers=headers)
data = response.json()

# Response format
{
    "price_history": [
        {
            "t": 1772000759000,  # timestamp ms
            "o": 2920.50,        # open
            "h": 2921.20,        # high
            "l": 2919.80,        # low
            "c": 2920.90,        # close
            "v": 45              # volume (lot count)
        },
        ...
    ]
}
```

---

## 🧪 Backtest dengan Data Exness

```python
import pandas as pd
from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy
from tools.fetch_exness_history import ExnessHistoryFetcher

# 1. Fetch data
fetcher = ExnessHistoryFetcher(account_id=..., token=...)
df = fetcher.fetch_range(
    symbol="XAUUSDm",
    timeframe="1h",
    start_date=datetime.now() - timedelta(days=30)
)

# 2. Convert to backtest format
df_bt = fetcher.convert_to_backtest_format(df)

# 3. Run backtest
strategy = XAUHedgingStrategy(config)
engine = BacktestEngine(initial_balance=10000, spread=0.04)
result = engine.run(strategy, df_bt)

# 4. Analyze
engine.print_report(result)
```

---

## ⚠️ Limitations & Notes

### Rate Limits
- Jangan fetch terlalu sering (delay 200-500ms per request)
- Max ~1000 candles per request
- Gunakan pagination untuk range besar

### Data Availability
- Trial accounts: Limited history
- Real accounts: Full history
- Data retention tergantung broker policy

### Timestamp Format
- Exness pakai **milliseconds** (not seconds)
- Contoh: `1772000759000` = Feb 25, 2026 12:45:59 UTC
- Python conversion: `int(datetime.timestamp() * 1000)`

### Timeframes Supported
| String | Value | Description |
|--------|-------|-------------|
| 1m | 1 | 1 minute |
| 5m | 5 | 5 minutes |
| 15m | 15 | 15 minutes |
| 30m | 30 | 30 minutes |
| 1h | 60 | 1 hour |
| 4h | 240 | 4 hours |
| 1d | 1440 | Daily |

---

## 🔄 Workflow Rekomendasi

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Fetch Data     │────▶│   Backtest      │────▶│  Paper Trading  │
│  (Exness API)   │     │  (Validate)     │     │  (Real-time)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │  Live Trading   │
                                                │  (Real Money)   │
                                                └─────────────────┘
```

1. **Fetch** historical data dari Exness (1-3 bulan)
2. **Backtest** dengan data tersebut
3. **Paper trade** untuk validasi real-time
4. **Live trade** dengan confidence lebih tinggi

---

## 📈 Perbandingan Hasil: Exness vs yfinance

### Hasil Backtest (Sample)

| Metric | Exness XAUUSDm | yfinance GC=F |
|--------|----------------|---------------|
| Initial Balance | $10,000 | $10,000 |
| Final Balance | $10,236 | $9,708 |
| Return | +2.36% | -2.92% |
| Total Trades | 1 | 73 |
| Win Rate | 100% | 30.1% |

**Insight**: Data yang berbeda menghasilkan hasil yang sangat berbeda! 
- Exness data lebih relevan untuk live trading
- yfinance (futures) memiliki volatilitas berbeda

---

## 🎯 Next Steps

1. **Get your JWT token** dari browser (lihat `examples/fetch_exness_data_demo.py`)
2. **Fetch 1-3 bulan data** untuk backtest yang meaningful
3. **Compare** hasil dengan yfinance data
4. **Optimize** parameter dengan data Exness
5. **Paper trade** untuk validasi
6. **Live trade** dengan confidence!

Selamat trading! 🚀
