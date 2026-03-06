"""
Complete System Demo - Shows all capabilities like MT5

Features demonstrated:
1. Backtest with historical data
2. Paper trading with real market data
3. Live trading with Exness Web API
4. Strategy automation
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy
from trading_bot.core.models import Config
from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.exchange.exness_web import create_exness_web_provider
from trading_bot.exchange.enhanced_exness import EnhancedExnessProvider
from trading_bot.exchange.paper_trading import PaperTradingProvider
from trading_bot.core.strategy_runner import StrategyRunner, RunnerConfig


def demo_backtest():
    """1. Backtest Demo"""
    print("\n" + "=" * 60)
    print("📊 DEMO 1: BACKTEST WITH HISTORICAL DATA")
    print("=" * 60)
    
    # Load data
    data_file = "data/xauusd_1mo_1h.csv"
    if not Path(data_file).exists():
        print("❌ Data file not found. Run: python tools/fetch_xau_data.py")
        return
        
    df = pd.read_csv(data_file)
    df.columns = [c.lower() for c in df.columns]
    
    # Setup
    config = Config(
        symbol="XAUUSD",
        lots=0.02,
        stop_loss=500,
        trailing=100,
        x_distance=50,
        max_spread=50
    )
    
    strategy = XAUHedgingStrategy(config, None)
    engine = BacktestEngine(
        initial_balance=10000,
        spread=0.04,
        commission=0.5  # $0.50 per lot
    )
    
    # Run
    result = engine.run(strategy, df, symbol="XAUUSD")
    
    # Report
    engine.print_report(result)
    
    # Save
    engine.save_report(result, "results/backtest_report.json")
    
    return result


def demo_paper_trading():
    """2. Paper Trading Demo"""
    print("\n" + "=" * 60)
    print("📈 DEMO 2: PAPER TRADING (DEMO MODE)")
    print("=" * 60)
    
    # This requires Exness credentials
    account_id = os.getenv("EXNESS_ACCOUNT_ID", "413461571")
    token = os.getenv("EXNESS_TOKEN")
    
    if not token:
        print("⚠️  Set EXNESS_TOKEN to run paper trading demo")
        print("   Skipping this demo...")
        return
        
    # Create providers
    data_provider = create_exness_web_provider(
        account_id=int(account_id),
        token=token,
        server="trial6"
    )
    
    paper_provider = PaperTradingProvider(
        data_provider=data_provider,
        initial_balance=10000,
        leverage=200
    )
    
    if not paper_provider.connect():
        print("❌ Failed to connect")
        return
        
    print(f"💰 Paper Balance: ${paper_provider.get_balance():.2f}")
    
    # Setup strategy and runner
    config = Config(
        symbol="XAUUSDm",
        lots=0.01,
        stop_loss=500,
        trailing=100
    )
    
    strategy = XAUHedgingStrategy(config, paper_provider)
    
    runner_config = RunnerConfig(
        symbol="XAUUSDm",
        enable_trading=True,
        max_positions=2,
        check_interval=5.0,
        session_filter=True
    )
    
    runner = StrategyRunner(strategy, paper_provider, runner_config)
    
    # Run for 60 seconds
    print("\n🚀 Running paper trading for 60 seconds...")
    runner.start()
    
    try:
        for i in range(6):
            time.sleep(10)
            print(f"   ... {i * 10}s elapsed")
            paper_provider.check_triggers()
            
        runner.stop()
        
    except KeyboardInterrupt:
        runner.stop()
        
    # Print results
    paper_provider.print_report()


def demo_live_trading():
    """3. Live Trading Demo (WARNING: Real money!)"""
    print("\n" + "=" * 60)
    print("💵 DEMO 3: LIVE TRADING (REAL MONEY)")
    print("=" * 60)
    
    print("⚠️  WARNING: This demo uses REAL MONEY!")
    print("   Set CONFIRM_LIVE=1 to actually execute trades")
    
    token = os.getenv("EXNESS_TOKEN")
    confirm = os.getenv("CONFIRM_LIVE")
    
    if not token:
        print("❌ Set EXNESS_TOKEN to run live trading")
        return
        
    if not confirm:
        print("⚠️  Set CONFIRM_LIVE=1 to enable live trading")
        print("   Running in DRY mode (no trades will be executed)")
        
    # Create provider
    provider = EnhancedExnessProvider(
        config=None  # Will use default config
    )
    
    # Get account summary
    summary = provider.get_account_summary()
    
    print("\n📊 Account Summary:")
    print(f"   Balance:      ${summary['balance']:.2f}")
    print(f"   Equity:       ${summary['equity']:.2f}")
    print(f"   Free Margin:  ${summary['free_margin']:.2f}")
    print(f"   Open Pos:     {summary['open_positions']}")
    
    # Show open positions
    positions = provider.get_positions()
    if positions:
        print("\n📋 Open Positions:")
        for pos in positions:
            print(f"   #{pos.id}: {pos.side.upper()} {pos.volume} lots @ {pos.entry_price}")
    
    # DRY MODE: Don't actually trade
    if not confirm:
        print("\n🚫 DRY MODE - No trades executed")
        print("   To trade live, set CONFIRM_LIVE=1")
        return
        
    # Live trading setup
    print("\n🚀 Starting LIVE trading...")
    
    # Example: Open a small test position
    price = provider.get_price("XAUUSDm")
    
    print(f"\nCurrent XAU/USD price: ${price:.2f}")
    print("Opening test position...")
    
    ticket = provider.open_position(
        symbol="XAUUSDm",
        side="long",
        volume=0.01,  # Micro lot
        sl=price - 5.0,  # $5 SL
        tp=price + 10.0  # $10 TP
    )
    
    if ticket:
        print(f"✅ Live position opened! Ticket: {ticket}")
        print("   Monitor in Exness Web Terminal")
    else:
        print("❌ Failed to open position")


def demo_strategy_automation():
    """4. Strategy Automation Demo"""
    print("\n" + "=" * 60)
    print("🤖 DEMO 4: STRATEGY AUTOMATION")
    print("=" * 60)
    
    print("This demo shows how to run a strategy 24/7")
    print("Uses paper trading for safety")
    
    token = os.getenv("EXNESS_TOKEN")
    if not token:
        print("⚠️  Set EXNESS_TOKEN to run automation demo")
        return
        
    # Setup
    data_provider = create_exness_web_provider(
        account_id=int(os.getenv("EXNESS_ACCOUNT_ID", "413461571")),
        token=token,
        server="trial6"
    )
    
    paper = PaperTradingProvider(data_provider, initial_balance=10000)
    
    config = Config(
        symbol="XAUUSDm",
        lots=0.01,
        stop_loss=500,
        trailing=200,
        break_even_profit=300,
        break_even_offset=100
    )
    
    strategy = XAUHedgingStrategy(config, paper)
    
    runner_config = RunnerConfig(
        symbol="XAUUSDm",
        timeframe="1m",
        enable_trading=True,
        max_positions=2,
        check_interval=1.0,
        session_filter=True,
        max_daily_loss=100,  # Stop if lose $100/day
        max_drawdown_pct=5,  # Stop if 5% drawdown
        on_trade_open=lambda t: print(f"🟢 Trade opened: {t}"),
        on_trade_close=lambda t: print(f"🔴 Trade closed: {t}"),
        on_error=lambda e: print(f"❌ Error: {e}")
    )
    
    runner = StrategyRunner(strategy, paper, runner_config)
    
    # Run for 2 minutes
    print("\n🚀 Running automated strategy for 2 minutes...")
    print("Press Ctrl+C to stop early\n")
    
    runner.start()
    
    try:
        for i in range(12):
            time.sleep(10)
            stats = paper.get_stats()
            print(f"   [{i*10}s] Equity: ${stats['equity']:.2f} | "
                  f"Trades: {stats['total_trades']} | "
                  f"Open: {stats['open_positions']}")
            
        runner.stop()
        
    except KeyboardInterrupt:
        print("\n⛔ Stopped by user")
        runner.stop()
        
    # Final report
    paper.print_report()
    runner.print_stats()


def main():
    """Run all demos"""
    print("=" * 60)
    print("🎯 EXNESS TRADING SYSTEM - COMPLETE DEMO")
    print("=" * 60)
    print("\nThis demo showcases:")
    print("  1. Backtest with historical data")
    print("  2. Paper trading (simulation)")
    print("  3. Live trading (real money)")
    print("  4. Strategy automation")
    
    # Run demos
    demo_backtest()
    # demo_paper_trading()  # Requires API token
    # demo_live_trading()   # Requires API token + confirmation
    # demo_strategy_automation()  # Requires API token
    
    print("\n" + "=" * 60)
    print("✅ Demo completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Get your Exness JWT token from browser")
    print("  2. Set EXNESS_TOKEN environment variable")
    print("  3. Run paper trading to test your strategy")
    print("  4. When ready, enable live trading")


if __name__ == "__main__":
    main()
