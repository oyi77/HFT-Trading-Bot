
# Exness Frontest (Demo Account) Guide

## Overview

Frontest mode with Exness uses a **real demo account** for testing, different from:
- **Paper trading**: Virtual/simulated (no real broker)
- **Ostium frontest**: Real testnet blockchain
- **Exness frontest**: Real Exness demo account with live market data

## Setup

### 1. Get Exness Demo Account

1. Sign up at [my.exness.com](https://my.exness.com)
2. Open a **Demo MT5** account
3. Note your:
   - Account ID (e.g., 413461571)
   - Server (e.g., trial6, trial5)
   - Password

### 2. Get API Token

1. Login to Exness Web Terminal
2. Open Developer Tools (F12)
3. Go to Network tab
4. Look for API requests to `rtapi-sg.eccweb.mobi`
5. Copy the **Authorization** Bearer token

### 3. Set Environment Variables

```bash
export EXNESS_ACCOUNT_ID="413461571"
export EXNESS_TOKEN="your_jwt_token_here"
export EXNESS_SERVER="trial6"  # or trial5, real17, etc.
```

### 4. Run Frontest

```bash
python trading_bot.py -i cli \
  --mode frontest \
  --provider exness \
  --symbol XAUUSDm \
  --lot 0.01 \
  --sl 500 \
  --tp 1000 \
  -y
```

## What Happens

- ✅ Connects to **real Exness demo server**
- ✅ Uses **live market prices** from Exness
- ✅ Opens **real positions** on demo account
- ✅ Real balance, margin, and PnL tracking
- ✅ Can verify trades in Exness Web Terminal

## Comparison

| Mode | Provider | Balance | Prices | Transactions |
|------|----------|---------|--------|--------------|
| Paper | Simulator | Virtual | Simulated | None |
| Frontest | Ostium | Real testnet USDC | Oracle | Blockchain |
| Frontest | Exness | Real demo | Live market | Broker demo |
| Real | Exness | Real money | Live market | Live broker |

## Troubleshooting

### "Failed to connect"
- Check token is valid (expires after ~24 hours)
- Verify account ID and server
- Ensure demo account is active

### "Insufficient balance"
- Demo accounts start with $10,000 virtual
- Can reset demo balance in Exness portal

