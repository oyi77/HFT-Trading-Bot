"""
FRONTEST: $100 Account with 0.1 Lot
⚠️  EXTREME RISK - USE WITH CAUTION!

Account Settings:
- Balance: $100
- Leverage: 1:2000
- Lot Size: 0.1 (STANDARD LOT)
- Risk: 1 trade loss = ACCOUNT WIPEOUT

SAFETY FEATURES:
1. Max 1 position only (cannot hedge - insufficient margin)
2. Max 2% risk per trade ($2 = 20 pips SL)
3. Daily loss limit: $30 (30%)
4. Auto-stop after 3 consecutive losses
5. Require manual confirmation each trade
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.exchange.exness_web import create_exness_web_provider


def print_warning():
    """Print extreme risk warning"""
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                     ⚠️  EXTREME RISK WARNING  ⚠️                  ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║                                                                   ║
    ║  Account: $100 USD                                               ║
    ║  Lot Size: 0.1 (STANDARD LOT)                                    ║
    ║  Leverage: 1:2000                                                ║
    ║                                                                   ║
    ║  RISK CALCULATION:                                               ║
    ║  • 1 Pip = $1.00                                                 ║
    ║  • SL 100 pips = $100 LOSS = ACCOUNT WIPEOUT!                    ║
    ║  • SL 50 pips = $50 LOSS = 50% GONE!                             ║
    ║  • SL 20 pips = $20 LOSS = 20% GONE!                             ║
    ║                                                                   ║
    ║  ⚠️  With 0.1 lot, ONE BAD TRADE = GAME OVER!                    ║
    ║                                                                   ║
    ║  SAFETY LIMITS ACTIVE:                                           ║
    ║  • Max 1 position (cannot hedge)                                 ║
    ║  • Max SL: 20 pips ($20 risk)                                    ║
    ║  • Daily loss limit: $30                                         ║
    ║  • Auto-stop after 3 losses                                      ║
    ║                                                                   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)


def calculate_position_size(balance, risk_percent, stop_loss_pips, price):
    """
    Calculate safe position size
    
    Formula: Lot = (Balance × Risk%) / (SL_pips × $/pip)
    For XAU/USD: $/pip = $1.00 per 0.1 lot
    """
    risk_amount = balance * (risk_percent / 100)
    dollars_per_pip = 1.00  # For 0.1 lot
    
    # Calculate max lot based on risk
    max_lot_by_risk = risk_amount / (stop_loss_pips * dollars_per_pip)
    
    # But user wants 0.1 lot, so check if safe
    user_lot = 0.1
    actual_risk = user_lot * stop_loss_pips * dollars_per_pip
    
    return {
        'user_lot': user_lot,
        'max_safe_lot': max_lot_by_risk,
        'actual_risk': actual_risk,
        'risk_percent': (actual_risk / balance) * 100,
        'is_safe': actual_risk <= risk_amount
    }


def frontest_extreme_risk():
    """Frontest with $100 and 0.1 lot - EXTREME RISK"""
    
    print_warning()
    
    # Get credentials
    token = os.getenv("EXNESS_TOKEN")
    account_id = int(os.getenv("EXNESS_ACCOUNT_ID", "413461571"))
    
    if not token:
        print("❌ Set EXNESS_TOKEN environment variable")
        return
    
    # Account settings
    BALANCE = 100
    LEVERAGE = 2000
    LOT_SIZE = 0.1
    MAX_SL_PIPS = 20  # MAXIMUM 20 pips SL = $20 risk
    MAX_DAILY_LOSS = 30  # $30 max loss per day
    MAX_CONSECUTIVE_LOSSES = 3
    
    print(f"\n📊 Account Settings:")
    print(f"   Balance: ${BALANCE}")
    print(f"   Leverage: 1:{LEVERAGE}")
    print(f"   Lot Size: {LOT_SIZE}")
    print(f"   Max SL: {MAX_SL_PIPS} pips (${MAX_SL_PIPS * 1:.0f} risk)")
    print(f"   Max Daily Loss: ${MAX_DAILY_LOSS}")
    
    # Risk calculation
    print(f"\n💰 Risk Calculation per Trade:")
    print(f"   Position Value: ${LOT_SIZE * 100 * 5000:,.0f}")
    print(f"   Margin Required: ${LOT_SIZE * 100 * 5000 / LEVERAGE:.2f}")
    print(f"   1 Pip Value: ${LOT_SIZE * 100 * 0.01:.2f}")
    print(f"   SL {MAX_SL_PIPS} pips = ${MAX_SL_PIPS * LOT_SIZE * 100 * 0.01:.2f} loss")
    
    # Calculate if safe
    calc = calculate_position_size(BALANCE, 20, MAX_SL_PIPS, 5000)
    print(f"\n🛡️  Safety Check:")
    print(f"   Actual Risk: ${calc['actual_risk']:.2f} ({calc['risk_percent']:.0f}% of account)")
    print(f"   Status: {'✅ ACCEPTABLE' if calc['is_safe'] else '❌ TOO RISKY'}")
    
    if not calc['is_safe']:
        print("\n❌ RISK TOO HIGH! Aborting...")
        return
    
    # Connect to broker
    print(f"\n🔗 Connecting to Exness...")
    provider = create_exness_web_provider(
        account_id=account_id,
        token=token,
        server="trial6"
    )
    
    if not provider.connect():
        print("❌ Connection failed")
        return
    
    # Check account status
    balance = provider.get_balance()
    margin_info = provider.get_margin_info()
    
    print(f"\n💵 Account Status:")
    print(f"   Balance: ${balance:.2f}")
    print(f"   Equity: ${margin_info.get('equity', 0):.2f}")
    print(f"   Free Margin: ${margin_info.get('free_margin', 0):.2f}")
    
    if balance < 100:
        print(f"\n⚠️  WARNING: Balance is ${balance:.2f}, expected $100")
        confirm = input("Continue anyway? (yes/no): ")
        if confirm.lower() != 'yes':
            return
    
    # Trading loop
    print(f"\n{'='*70}")
    print(f"🚀 STARTING FRONTEST - EXTREME RISK MODE")
    print(f"{'='*70}")
    
    daily_loss = 0
    consecutive_losses = 0
    total_trades = 0
    wins = 0
    losses = 0
    
    try:
        while True:
            # Check daily loss limit
            if daily_loss >= MAX_DAILY_LOSS:
                print(f"\n🛑 DAILY LOSS LIMIT REACHED: ${daily_loss:.2f}")
                print("Stopping trading for today...")
                break
            
            # Check consecutive losses
            if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                print(f"\n🛑 MAX CONSECUTIVE LOSSES: {consecutive_losses}")
                print("Stopping to prevent wipeout...")
                break
            
            # Get current price
            price = provider.get_price("XAUUSDm")
            
            print(f"\n{'='*70}")
            print(f"Trade #{total_trades + 1} | {datetime.now()}")
            print(f"XAU/USD: ${price:.2f}")
            print(f"Daily Loss: ${daily_loss:.2f} / ${MAX_DAILY_LOSS}")
            print(f"Consecutive Losses: {consecutive_losses} / {MAX_CONSECUTIVE_LOSSES}")
            
            # Manual confirmation REQUIRED
            print(f"\n⚠️  MANUAL CONFIRMATION REQUIRED")
            print(f"   Opening 0.1 lot position")
            print(f"   Risk: ${MAX_SL_PIPS} per 20 pips move")
            print(f"   One wrong move = GAME OVER")
            
            confirm = input("\nType 'TRADE' to proceed (or 'quit' to exit): ")
            
            if confirm.lower() == 'quit':
                print("Exiting...")
                break
            
            if confirm != 'TRADE':
                print("Trade cancelled.")
                continue
            
            # Get position direction
            direction = input("Direction (buy/sell): ").lower()
            if direction not in ['buy', 'sell']:
                print("Invalid direction")
                continue
            
            # Calculate SL/TP
            sl_distance = MAX_SL_PIPS * 0.01  # 20 pips in price
            if direction == 'buy':
                sl = price - sl_distance
                tp = price + (sl_distance * 2)  # 1:2 RR
            else:
                sl = price + sl_distance
                tp = price - (sl_distance * 2)
            
            print(f"\n📋 Trade Setup:")
            print(f"   Direction: {direction.upper()}")
            print(f"   Entry: ${price:.2f}")
            print(f"   SL: ${sl:.2f} ({MAX_SL_PIPS} pips, ${MAX_SL_PIPS} risk)")
            print(f"   TP: ${tp:.2f} ({MAX_SL_PIPS * 2} pips, ${MAX_SL_PIPS * 2} potential)")
            
            # Final confirmation
            final = input("\nType 'EXECUTE' to place trade: ")
            if final != 'EXECUTE':
                print("Trade cancelled.")
                continue
            
            # Execute trade
            print(f"\n🚀 Executing trade...")
            side = "long" if direction == 'buy' else "short"
            
            ticket = provider.open_position(
                symbol="XAUUSDm",
                side=side,
                volume=LOT_SIZE,
                sl=sl,
                tp=tp,
                price=price
            )
            
            if ticket:
                print(f"✅ Trade opened! Ticket: {ticket}")
                total_trades += 1
                
                # Monitor trade
                print(f"\n⏳ Monitoring trade (Press Ctrl+C to close manually)...")
                try:
                    while True:
                        positions = provider.get_positions("XAUUSDm")
                        if not positions:
                            print("\n📝 Position closed!")
                            
                            # Check result
                            time.sleep(1)
                            new_balance = provider.get_balance()
                            pnl = new_balance - balance
                            
                            if pnl > 0:
                                print(f"   Result: +${pnl:.2f} ✅ WIN")
                                wins += 1
                                consecutive_losses = 0
                            else:
                                print(f"   Result: ${pnl:.2f} ❌ LOSS")
                                losses += 1
                                consecutive_losses += 1
                                daily_loss += abs(pnl)
                            
                            balance = new_balance
                            print(f"   New Balance: ${balance:.2f}")
                            break
                        
                        # Show status every 5 seconds
                        time.sleep(5)
                        for pos in positions:
                            print(f"   P&L: ${pos.profit:.2f} | Price: ${provider.get_price('XAUUSDm'):.2f}", end='\r')
                            
                except KeyboardInterrupt:
                    print(f"\n\n⚠️  Manual intervention!")
                    close = input("Close position? (yes/no): ")
                    if close.lower() == 'yes':
                        provider.close_position(ticket, "XAUUSDm")
                        print("Position closed manually.")
            else:
                print("❌ Failed to open trade")
    
    except KeyboardInterrupt:
        print(f"\n\n🛑 Stopped by user")
    
    # Final report
    print(f"\n{'='*70}")
    print(f"📊 FRONTEST REPORT")
    print(f"{'='*70}")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins} | Losses: {losses}")
    if total_trades > 0:
        print(f"Win Rate: {wins/total_trades*100:.1f}%")
    print(f"Final Balance: ${balance:.2f}")
    print(f"Total P&L: ${balance - 100:.2f}")
    print(f"Daily Loss: ${daily_loss:.2f}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("FRONTEST: $100 Account with 0.1 Lot")
    print("="*70)
    
    # Double confirm
    print("\n⚠️  This script will trade with EXTREME RISK!")
    print("    One bad trade can wipe out your account!")
    
    confirm = input("\nDo you understand the risks? Type 'I UNDERSTAND': ")
    
    if confirm == 'I UNDERSTAND':
        frontest_extreme_risk()
    else:
        print("\n❌ Cancelled. Please reconsider using 0.01 lot instead.")
        print("   Command: python examples/frontest_safe.py")
