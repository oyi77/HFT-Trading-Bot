"""
Demo: Fetch Historical Data from Exness API

This shows how to fetch real XAU/USD historical data directly from Exness,
which is more accurate than yfinance because:
1. Same price feed as live trading
2. Real spread data (bid/ask)
3. Same instrument specifications (XAUUSDm)
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.exchange.exness_web import create_exness_web_provider
from tools.fetch_exness_history import ExnessHistoryFetcher


def demo_fetch_latest_candles():
    """1. Fetch latest candles (for live trading reference)"""
    print("=" * 60)
    print("📊 DEMO 1: Fetch Latest Candles")
    print("=" * 60)
    
    token = os.getenv("EXNESS_TOKEN")
    if not token:
        print("❌ Set EXNESS_TOKEN environment variable")
        return
    
    # Create provider
    provider = create_exness_web_provider(
        account_id=int(os.getenv("EXNESS_ACCOUNT_ID", "413461571")),
        token=token,
        server="trial6"
    )
    
    # Fetch latest 100 1-minute candles
    candles = provider.get_candles("XAUUSDm", timeframe="1m", limit=100)
    
    print(f"\n✅ Fetched {len(candles)} candles")
    if candles:
        print(f"   First: {datetime.fromtimestamp(candles[0]['timestamp']/1000)}")
        print(f"   Last:  {datetime.fromtimestamp(candles[-1]['timestamp']/1000)}")
        print(f"\n📋 Sample:")
        for c in candles[-5:]:
            ts = datetime.fromtimestamp(c['timestamp']/1000)
            print(f"   {ts}: O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f}")


def demo_fetch_historical_range():
    """2. Fetch historical data for backtesting"""
    print("\n" + "=" * 60)
    print("📈 DEMO 2: Fetch Historical Range for Backtest")
    print("=" * 60)
    
    token = os.getenv("EXNESS_TOKEN")
    if not token:
        print("❌ Set EXNESS_TOKEN environment variable")
        return
    
    # Create fetcher
    fetcher = ExnessHistoryFetcher(
        account_id=int(os.getenv("EXNESS_ACCOUNT_ID", "413461571")),
        token=token,
        server="trial6"
    )
    
    # Fetch 3 days of 1-hour candles
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)
    
    df = fetcher.fetch_range(
        symbol="XAUUSDm",
        timeframe="1h",
        start_date=start_date,
        end_date=end_date
    )
    
    if not df.empty:
        print(f"\n✅ Fetched {len(df)} candles")
        print(f"\n📊 Statistics:")
        print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"   Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
        print(f"   Avg close: ${df['close'].mean():.2f}")
        
        # Save for backtest
        fetcher.save_to_csv(df, "data/exness_xauusd_3d.csv")
        print(f"\n💾 Data saved for backtesting!")


def demo_fetch_specific_date():
    """3. Fetch specific date range (Feb 25, 2026 as shown in traced data)"""
    print("\n" + "=" * 60)
    print("📅 DEMO 3: Fetch Specific Date (Feb 25, 2026)")
    print("=" * 60)
    
    token = os.getenv("EXNESS_TOKEN")
    if not token:
        print("❌ Set EXNESS_TOKEN environment variable")
        return
    
    provider = create_exness_web_provider(
        account_id=int(os.getenv("EXNESS_ACCOUNT_ID", "413461571")),
        token=token,
        server="trial6"
    )
    
    # From the traced data: from=1772000759000 (Feb 25, 2026 ~12:45 UTC)
    # This is a future timestamp in their system (year 2026)
    from_ts = 1772000759000
    
    print(f"\n📡 Fetching from timestamp: {from_ts}")
    print(f"   Date: {datetime.fromtimestamp(from_ts/1000)} UTC")
    
    # Fetch 968 candles backwards from that timestamp (like in traced data)
    candles = provider.get_candles(
        symbol="XAUUSDm",
        timeframe="1m",
        limit=968,
        from_time=from_ts
    )
    
    print(f"\n✅ Fetched {len(candles)} 1-minute candles")
    if candles:
        print(f"   Range: {datetime.fromtimestamp(candles[0]['timestamp']/1000)}")
        print(f"          to {datetime.fromtimestamp(candles[-1]['timestamp']/1000)}")
        
        # Calculate price movement
        start_price = candles[0]['open']
        end_price = candles[-1]['close']
        change = end_price - start_price
        change_pct = (change / start_price) * 100
        
        print(f"\n📈 Price Movement:")
        print(f"   Start: ${start_price:.2f}")
        print(f"   End:   ${end_price:.2f}")
        print(f"   Change: ${change:+.2f} ({change_pct:+.3f}%)")


def demo_backtest_with_exness_data():
    """4. Run backtest with Exness data"""
    print("\n" + "=" * 60)
    print("🧪 DEMO 4: Backtest with Exness Data")
    print("=" * 60)
    
    import pandas as pd
    from trading_bot.core.backtest_engine import BacktestEngine
    from trading_bot.strategy.xau_hedging import XAUHedgingStrategy
    from trading_bot.core.models import Config
    
    token = os.getenv("EXNESS_TOKEN")
    if not token:
        print("❌ Set EXNESS_TOKEN environment variable")
        return
    
    # Fetch data
    fetcher = ExnessHistoryFetcher(
        account_id=int(os.getenv("EXNESS_ACCOUNT_ID", "413461571")),
        token=token,
        server="trial6"
    )
    
    print("\n📡 Fetching data from Exness...")
    df = fetcher.fetch_range(
        symbol="XAUUSDm",
        timeframe="1h",
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now()
    )
    
    if df.empty:
        print("❌ No data fetched")
        return
    
    # Convert to backtest format
    df_bt = fetcher.convert_to_backtest_format(df)
    
    # Setup strategy
    config = Config(
        symbol="XAUUSDm",
        lots=0.02,
        stop_loss=500,
        trailing=200
    )
    strategy = XAUHedgingStrategy(config)
    engine = BacktestEngine(initial_balance=10000, spread=0.04)
    
    # Run backtest
    print("\n🚀 Running backtest...")
    result = engine.run(strategy, df_bt, symbol="XAUUSDm")
    
    # Report
    engine.print_report(result)
    
    # Compare with yfinance data
    print("\n📊 Comparison with yfinance:")
    print("   Exness data: Real broker data, same as live trading")
    print("   yfinance:    Gold futures (GC=F), different price")
    print(f"   Exness XAU:  ~$2900-3000 (typical spot price)")
    print(f"   GC=Futures:  ~$4600-5400 (futures contract)")


def print_usage():
    """Print usage instructions"""
    print("""
🔑 How to get your Exness JWT Token:

1. Login to https://my.exness.com
2. Open Web Terminal (click "Trade" on any account)
3. Open Developer Tools (F12 or Cmd+Option+I)
4. Go to "Network" tab
5. Look for any request to "rtapi-sg.eccweb.mobi"
6. Click the request and find "Authorization" header
7. Copy the token (starts with "Bearer eyJhbGci...")
8. Set as environment variable:
   export EXNESS_TOKEN="eyJhbGciOiJSUzI1NiIs..."

⚠️  IMPORTANT: Keep your token secure! Never commit it to git!
    """)


def main():
    """Run all demos"""
    print("=" * 60)
    print("🎯 EXNESS HISTORICAL DATA FETCHER DEMO")
    print("=" * 60)
    
    # Check token
    if not os.getenv("EXNESS_TOKEN"):
        print("\n❌ EXNESS_TOKEN not set!")
        print_usage()
        return
    
    print("\n✅ Token found! Running demos...\n")
    
    # Run demos
    demo_fetch_latest_candles()
    demo_fetch_historical_range()
    demo_fetch_specific_date()
    demo_backtest_with_exness_data()
    
    print("\n" + "=" * 60)
    print("✅ All demos completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Use Exness data for more accurate backtesting")
    print("  2. Compare results between Exness and yfinance")
    print("  3. Use same data source for backtest AND live trading")


if __name__ == "__main__":
    main()
