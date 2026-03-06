# 📊 Leverage Analysis & Risk Management

## ⚠️ LEVERAGE IS CRITICAL - Test Results

### Test: $100 Account dengan Berbagai Leverage

| Leverage | Margin Req | Trades | Return | Status |
|----------|-----------|--------|--------|--------|
| **1:50** | $50/lot | **0** | **0%** | ❌ TOO LOW |
| 1:100 | $25/lot | 106 | +406% | ✅ OK |
| 1:200 | $12.50/lot | 106 | +406% | ✅✅ OPTIMAL |
| 1:500 | $5/lot | 106 | +406% | ✅ SAFE |
| 1:1000 | $2.50/lot | 106 | +406% | ⚠️ RISKY |

### 🚨 Key Finding: Leverage 1:50 = NO TRADES!

Dengan leverage 1:50 dan 0.005 lot:
- Margin required: $50 per posisi
- Dengan buffer 3x: perlu $150 free margin
- Account hanya $100 → **TIDAK BISA TRADE!**

---

## 🔢 Formula Margin Calculation

```
Margin = (Volume × Contract Size × Price) / Leverage

Untuk XAU/USD:
• Contract Size: 100 oz
• Price: ~$5,000
• Volume: 0.005 lot (5 oz)

Contoh perhitungan:
• 1:50  → (0.005 × 100 × 5000) / 50   = $50
• 1:200 → (0.005 × 100 × 5000) / 200  = $12.50
• 1:500 → (0.005 × 100 × 5000) / 500  = $5
```

---

## 💡 Optimal Leverage by Account Size

### Account $100

| Lot Size | Min Leverage | Recommended | Max Leverage |
|----------|-------------|-------------|--------------|
| 0.001 (micro) | 1:50 | 1:100-200 | 1:500 |
| 0.005 (mini) | 1:100 | **1:200-500** | 1:1000 |
| 0.01 (standard) | 1:200 | 1:500-1000 | ⚠️ Too risky |

**Best for $100: Leverage 1:200-1:500**

### Account $1000

| Lot Size | Min Leverage | Recommended | Max Leverage |
|----------|-------------|-------------|--------------|
| 0.01 | 1:50 | 1:100-200 | 1:500 |
| 0.02 | 1:100 | **1:200** | 1:500 |
| 0.05 | 1:200 | 1:500 | 1:1000 |

**Best for $1000: Leverage 1:200**

### Account $10000

| Lot Size | Min Leverage | Recommended | Notes |
|----------|-------------|-------------|-------|
| 0.1 | 1:50 | **1:200** | Standard |
| 0.2 | 1:100 | 1:200 | Higher risk |
| 0.5 | 1:200 | 1:500 | Very high risk |

**Best for $10000: Leverage 1:200**

---

## 🛡️ Risk Levels by Leverage

### Conservative (1:50 - 1:100)
```
✅ Pros:
   • Low risk of margin call
   • More buffer for drawdown
   • Better for beginners

❌ Cons:
   • Need larger account for same position size
   • Lower buying power
   • May not be able to open multiple positions
```

### Moderate (1:200 - 1:500) ⭐ RECOMMENDED
```
✅ Pros:
   • Good balance risk/reward
   • Sufficient for hedging strategies
   • Can open 2-3 positions with buffer
   • Most common broker offering

⚠️ Cons:
   • Still need proper risk management
   • Can get margin call if not careful
```

### Aggressive (1:1000+)
```
⚠️ Pros:
   • Maximum buying power
   • Can open many positions
   • Low margin requirement

❌ Cons:
   • HIGH risk of margin call
   • Small drawdown = liquidated
   • Not recommended for hedging
   • Often banned by regulated brokers
```

---

## 📋 Implementation di Code

### 1. Margin Check Sebelum Open Position

```python
def can_open_position(equity, lot_size, price, leverage, buffer=3):
    """
    Check if we have sufficient margin
    
    Args:
        equity: Current account equity
        lot_size: Position volume (e.g., 0.005)
        price: Current market price
        leverage: Account leverage (e.g., 200)
        buffer: Safety multiplier (default 3x)
    
    Returns:
        bool: True if can open position
    """
    contract_size = 100  # XAU/USD
    margin_required = (lot_size * contract_size * price) / leverage
    
    # Need buffer for drawdown
    return equity > margin_required * buffer
```

### 2. Calculate Margin Level

```python
def calculate_margin_level(equity, margin_used):
    """
    Calculate margin level percentage
    
    Margin Call: < 100%
    Stop Out: < 20-50% (depends on broker)
    """
    if margin_used == 0:
        return float('inf')
    return (equity / margin_used) * 100
```

### 3. Auto Lot Size based on Leverage

```python
def calculate_safe_lot_size(equity, price, leverage, risk_percent=10):
    """
    Calculate safe lot size based on available margin
    
    Risk 10% of equity max per position
    """
    contract_size = 100
    max_margin = equity * (risk_percent / 100)
    
    # Max lot = (Max Margin × Leverage) / (Contract × Price)
    max_lot = (max_margin * leverage) / (contract_size * price)
    
    # Round down to lot step (0.001)
    return math.floor(max_lot / 0.001) * 0.001
```

---

## ⚠️ Broker Settings yang Perlu Di-check

### 1. Margin Call Level
```
Typical: 100%
Meaning: When Equity = Margin Used
Action: Cannot open new positions
```

### 2. Stop Out Level
```
Typical: 20-50%
Meaning: When Margin Level < 20-50%
Action: Force close positions (liquidation)

Exness: 0% (no stop out - negative balance possible)
Others: 20-50%
```

### 3. Hedged Margin
```
Some brokers: Full margin for both positions
Others: 50% margin for hedged positions
Exness: 0% margin for fully hedged (check account type)
```

---

## 🎯 Exness Specific

### Account Types & Leverage

| Account Type | Max Leverage | Margin Call | Stop Out |
|-------------|-------------|-------------|----------|
| Standard | 1:Unlimited | 60% | 0% |
| Pro | 1:Unlimited | 30% | 0% |
| Zero | 1:Unlimited | 30% | 0% |
| Raw Spread | 1:Unlimited | 30% | 0% |

### Exness Advantages
```
✅ No stop out (0%) - positions stay open until margin recovered
✅ Negative balance protection
✅ High leverage available (up to 1:Unlimited)
✅ 0% margin for fully hedged positions (some account types)
```

### Exness Risks
```
⚠️ Unlimited leverage = unlimited risk if not managed
⚠️ Can go negative balance (but protected)
⚠️ Swap charges apply overnight
```

---

## 📝 Code Update untuk Handle Leverage

```python
class BacktestEngine:
    def __init__(self, initial_balance=10000, leverage=200):
        self.balance = initial_balance
        self.equity = initial_balance
        self.leverage = leverage
        self.margin_used = 0
        
        # Broker settings
        self.margin_call_level = 100  # 100%
        self.stop_out_level = 0       # 0% for Exness
        
    def calculate_margin(self, volume, price):
        """Calculate required margin for position"""
        contract_size = 100  # XAU/USD
        return (volume * contract_size * price) / self.leverage
    
    def check_margin_level(self):
        """Check current margin level"""
        if self.margin_used == 0:
            return float('inf')
        return (self.equity / self.margin_used) * 100
    
    def can_open_position(self, volume, price, buffer=3):
        """Check if sufficient margin available"""
        margin_needed = self.calculate_margin(volume, price)
        free_margin = self.equity - self.margin_used
        return free_margin >= margin_needed * buffer
    
    def check_stop_out(self):
        """Check if stop out triggered"""
        margin_level = self.check_margin_level()
        return margin_level <= self.stop_out_level
```

---

## 🎓 Best Practices

### 1. Never Use Max Leverage
```
❌ Account $100, leverage 1:1000, open 0.1 lot
   Margin: $50, Free: $50
   Price drops 1% = Margin call!

✅ Account $100, leverage 1:200, open 0.01 lot
   Margin: $25, Free: $75
   Buffer untuk drawdown 75%
```

### 2. Keep Margin Level > 200%
```
Margin Level = (Equity / Margin Used) × 100

Target: > 200%
Warning: < 100%
Danger: < 50%
```

### 3. Calculate Before Trading
```
Before open position:
1. Calculate margin required
2. Check free margin
3. Ensure buffer > 3x
4. Check margin level > 200%
```

---

## ✅ Checklist untuk Live Trading

- [ ] Know your leverage (check broker settings)
- [ ] Know margin call level (typically 100%)
- [ ] Know stop out level (Exness: 0%, others: 20-50%)
- [ ] Calculate margin before every trade
- [ ] Keep margin level > 200%
- [ ] Never risk more than 10% equity per trade
- [ ] Monitor margin level continuously
- [ ] Have stop loss to limit drawdown

---

## 🚀 Summary

**Untuk $100 Account di Exness:**
```
✅ Minimum Leverage: 1:100
✅✅ Recommended: 1:200-1:500
❌ Avoid: 1:50 (cannot trade), 1:1000+ (too risky)

✅ Optimal Lot Size: 0.005
✅ Margin per position: $12.50 (1:200)
✅ Buffer: 8x ($100 / $12.50)
✅ Safe untuk hedging
```

**Code sudah di-update untuk:**
1. ✅ Check margin sebelum open position
2. ✅ Calculate margin level
3. ✅ Handle margin call
4. ✅ Handle stop out
5. ✅ Adjustable leverage parameter

---

*Analysis Date: 2026-03-05*
*Broker: Exness*
*Account: Trial/Demo*
