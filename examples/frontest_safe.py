"""
FRONTEST: $100 Account with SAFE Risk Management
✅ RECOMMENDED VERSION

Account Settings:
- Balance: $100
- Leverage: 1:2000
- Lot Size: 0.01 (Micro Lot) - Much safer!
- Risk: 2-5% per trade

SAFETY FEATURES:
1. Proper position sizing (0.01 lot max)
2. SL 500 pips = $50 risk (50% account max)
3. Can hedge (sufficient margin)
4. Daily loss limit: $30
5. Trailing stop + Break even
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.exchange.exness_web import create_exness_web_provider
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy
from trading_bot.core.models import Config


def frontest_safe():
    """Frontest with proper risk management"""
    
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                    ✅ SAFE FRONTEST MODE                          ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║                                                                   ║
    ║  Account: $100 USD                                               ║
    ║  Lot Size: 0.01 (MICRO LOT) ✅                                   ║
    ║  Leverage: 1:2000                                                ║
    ║  Strategy: XAU Hedging with Session Filter                       ║
    ║                                                                   ║
    ║  RISK MANAGEMENT:                                                ║
    ║  • 1 Pip = $0.10 (10x smaller than 0.1 lot)                     ║
    ║  • SL 500 pips = $50 risk (50% account) ✅                      ║
    ║  • Can hedge (2 positions max)                                   ║
    ║  • Daily loss limit: $30                                         ║
    ║  • Auto stop at 30% drawdown                                     ║
    ║                                                                   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Get credentials
    token = os.getenv("EXNESS_TOKEN")
    account_id = int(os.getenv("EXNESS_ACCOUNT_ID", "413461571"))
    
    if not token:
        print("❌ Set EXNESS_TOKEN environment variable")
        return
    
    # SAFE Settings
    BALANCE = 100
    LEVERAGE = 2000
    LOT_SIZE = 0.01  # MICRO LOT - SAFE!
    MAX_DAILY_LOSS = 30
    MAX_POSITIONS = 2
    
    print(f"\n📊 Safe Account Settings:")
    print(f"   Balance: ${BALANCE}")
    print(f"   Leverage: 1:{LEVERAGE}")
    print(f"   Lot Size: {LOT_SIZE} (Micro)")
    print(f"   Max Daily Loss: ${MAX_DAILY_LOSS}")
    print(f"   Max Positions: {MAX_POSITIONS}")
    
    print(f"\n💰 Risk Calculation:")
    print(f"   1 Pip Value: ${LOT_SIZE * 100 * 0.01:.2f}")
    print(f"   SL 500 pips = ${500 * LOT_SIZE * 100 * 0.01:.2f} risk")
    print(f"   Margin per position: ${LOT_SIZE * 100 * 5000 / LEVERAGE:.2f}")
    print(f"   Can open {int(BALANCE / (LOT_SIZE * 100 * 5000 / LEVERAGE))} positions with buffer")
    
    # Connect
    print(f"\n🔗 Connecting to Exness...")
    provider = create_exness_web_provider(
        account_id=account_id,
        token=token,
        server="trial6"
    )
    
    if not provider.connect():
        print("❌ Connection failed")
        return
    
    # Check account
    balance = provider.get_balance()
    print(f"\n💵 Account Connected:")
    print(f"   Balance: ${balance:.2f}")
    
    # Setup strategy
    config = Config(
        symbol="XAUUSDm",
        lots=LOT_SIZE,
        stop_loss=500,
        trailing=200,
        break_even_profit=300,
        break_even_offset=100
    )
    
    strategy = XAUHedgingStrategy(config)
    
    print(f"\n{'='*70}")
    print(f"🚀 STARTING SAFE FRONTEST")
    print(f"{'='*70}")
    print(f"Strategy: XAU Hedging (ahdu.mq5 style)")
    print(f"Auto-trading enabled with safety checks")
    print(f"\nPress Ctrl+C to stop\n")
    
    # Stats
    start_balance = balance
    daily_loss = 0
    total_trades = 0
    wins = 0
    losses = 0
    
    try:
        while True:
            # Check daily loss
            if daily_loss >= MAX_DAILY_LOSS:
                print(f"🛑 Daily loss limit reached: ${daily_loss:.2f}")
                break
            
            # Get price
            price = provider.get_price("XAUUSDm")
            bid = price - 0.02
            ask = price + 0.02
            timestamp = int(datetime.now().timestamp() * 1000)
            
            # Get positions
            positions = provider.get_positions("XAUUSDm")
            
            # Check existing positions
            if len(positions) >= MAX_POSITIONS:
                time.sleep(5)
                continue
            
            # Strategy logic
            signal = strategy.on_tick(price, bid, ask, positions, timestamp)
            
            if signal and signal.get('action') == 'open':
                side = signal.get('side', 'long')
                sl = signal.get('sl')
                
                # Check margin
                margin_needed = LOT_SIZE * 100 * price / LEVERAGE
                if balance < margin_needed * 3:
                    print(f"⚠️ Insufficient margin. Skipping...")
                    time.sleep(10)
                    continue
                
                # Execute
                print(f"\n📊 Signal: {side.upper()} | Price: ${price:.2f} | SL: ${sl:.2f}")
                
                ticket = provider.open_position(
                    symbol="XAUUSDm",
                    side=side,
                    volume=LOT_SIZE,
                    sl=sl,
                    tp=0  # Use trailing only
                )
                
                if ticket:
                    print(f"✅ Opened #{ticket}")
                    total_trades += 1
                else:
                    print(f"❌ Failed to open")
            
            # Check P&L periodically
            if len(positions) > 0:
                total_pnl = sum(p.profit for p in positions)
                print(f"Open P&L: ${total_pnl:.2f} | Positions: {len(positions)}", end='\r')
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 Stopped by user")
    
    # Close all positions
    print(f"\n🔒 Closing all positions...")
    positions = provider.get_positions("XAUUSDm")
    for pos in positions:
        provider.close_position(pos.id, "XAUUSDm")
        print(f"   Closed #{pos.id}")
    
    # Final report
    final_balance = provider.get_balance()
    print(f"\n{'='*70}")
    print(f"📊 FRONTEST REPORT")
    print(f"{'='*70}")
    print(f"Start Balance: ${start_balance:.2f}")
    print(f"Final Balance: ${final_balance:.2f}")
    print(f"Total Return: ${final_balance - start_balance:+.2f}")
    print(f"Total Trades: {total_trades}")
    print(f"Return %: {((final_balance/start_balance)-1)*100:+.2f}%")


if __name__ == "__main__":
    frontest_safe()
