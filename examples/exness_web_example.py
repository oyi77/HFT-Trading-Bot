"""
Example: Using Exness Web Trading API Provider

This shows how to connect directly to Exness Web Terminal API
based on reverse-engineered endpoints from docs/EXNESS_TRACED.md

IMPORTANT: You need to obtain a JWT token from the browser:
1. Login to https://my.exness.com
2. Open Web Terminal
3. Open DevTools (F12) → Network tab
4. Look for any request to rtapi-sg.eccweb.mobi
5. Copy the Authorization Bearer token
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.exchange.exness_web import create_exness_web_provider


def main():
    # Get credentials from environment or input
    # NEVER hardcode tokens in production!
    account_id = int(os.getenv("EXNESS_ACCOUNT_ID", "413461571"))
    token = os.getenv("EXNESS_TOKEN")
    server = os.getenv("EXNESS_SERVER", "trial6")  # trial6, trial5, real17, etc
    
    if not token:
        print("❌ Please set EXNESS_TOKEN environment variable")
        print("   Get token from browser DevTools as described in the docstring")
        return
    
    print("=" * 60)
    print("🔗 EXNESS WEB TRADING API EXAMPLE")
    print("=" * 60)
    
    # Create provider
    provider = create_exness_web_provider(
        account_id=account_id,
        token=token,
        server=server
    )
    
    # Test connection
    print("\n1. Testing connection...")
    if not provider.connect():
        print("Failed to connect!")
        return
    
    # Get account info
    print("\n2. Account Info:")
    info = provider.get_account_info()
    print(f"   Account: {info.get('account_id')}")
    print(f"   Currency: {info.get('settings', {}).get('currency')}")
    print(f"   Leverage: 1:{info.get('settings', {}).get('leverage')}")
    
    # Get balance
    print("\n3. Balance Info:")
    margin = provider.get_margin_info()
    print(f"   Balance: ${margin.get('balance', 0):,.2f}")
    print(f"   Equity:  ${margin.get('equity', 0):,.2f}")
    print(f"   Margin:  ${margin.get('margin', 0):,.2f}")
    print(f"   Free:    ${margin.get('free_margin', 0):,.2f}")
    
    # Get positions
    print("\n4. Open Positions:")
    positions = provider.get_positions()
    if positions:
        for pos in positions:
            print(f"   #{pos.id}: {pos.side.upper()} {pos.volume} lots @ {pos.entry_price}")
            print(f"       SL: {pos.sl} | TP: {pos.tp} | P&L: ${pos.profit:.2f}")
    else:
        print("   No open positions")
    
    # Get XAUUSD price
    print("\n5. XAU/USD Price:")
    price = provider.get_price("XAUUSDm")
    print(f"   Current: ${price:.2f}")
    
    # Get recent candles
    print("\n6. Recent Candles (1H):")
    candles = provider.get_candles("XAUUSDm", timeframe="1h", limit=5)
    for c in candles[-5:]:
        ts = c['timestamp'] / 1000
        print(f"   {ts}: O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f}")
    
    # Example: Open a trade (commented out for safety)
    # print("\n7. Opening test trade...")
    # ticket = provider.open_position(
    #     symbol="XAUUSDm",
    #     side="long",
    #     volume=0.01,
    #     sl=price - 5.0,  # $5 stop loss
    # )
    # print(f"   Ticket: {ticket}")
    
    print("\n" + "=" * 60)
    print("✅ Done! Check the code to see how to place actual trades.")


if __name__ == "__main__":
    main()
