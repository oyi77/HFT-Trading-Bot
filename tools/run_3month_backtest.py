"""
3-Month Strategy Comparison Backtest
Runs ALL strategies on 3 months of real XAU/USD H1 data
Outputs ranked comparison table
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime

from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.hft import HFTStrategy, HFTConfig
from trading_bot.strategy.seven_candle import SevenCandleStrategy, SevenCandleConfig
from trading_bot.strategy.zerolag import ZeroLagStrategy, ZeroLagConfig
from trading_bot.strategy.ai_strategy import AIStrategy, AIStrategyConfig
from trading_bot.strategy.bb_macd_rsi import BBMacdRsiStrategy, BBMacdRsiConfig
from trading_bot.strategy.scalping import ScalpingStrategy, ScalpingConfig


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    
    # Ensure columns exist
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ('open', 'high', 'low', 'close', 'volume', 'timestamp'):
            col_map[c] = cl
    df.rename(columns=col_map, inplace=True)
    
    # Create timestamp if missing
    if 'timestamp' not in df.columns:
        for col in ['datetime', 'Datetime', 'Date', 'date']:
            if col in df.columns:
                df['timestamp'] = pd.to_datetime(df[col]).astype(int) // 10**6
                break
    
    # Ensure numeric
    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
    
    if 'volume' not in df.columns:
        df['volume'] = 100
    
    return df


def run_strategy_backtest(name, strategy, data, initial_balance=10000, leverage=200):
    """Run backtest for a single strategy"""
    engine = BacktestEngine(
        initial_balance=initial_balance,
        leverage=leverage,
        spread=0.30,  # XAU typical spread ~$0.30
        commission=0,
        slippage=0.05
    )
    
    try:
        result = engine.run(strategy, data, symbol="XAUUSD")
        return {
            'name': name,
            'return_pct': result.total_return_pct,
            'final_balance': result.final_balance,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'sharpe': result.sharpe_ratio,
            'sortino': result.sortino_ratio,
            'max_dd_pct': result.max_drawdown_pct,
            'avg_trade': result.avg_trade,
            'largest_profit': result.largest_profit,
            'largest_loss': result.largest_loss,
            'max_consec_wins': result.max_consecutive_wins,
            'max_consec_losses': result.max_consecutive_losses,
            'avg_duration_min': result.avg_trade_duration,
            'net_profit': result.net_profit,
            'status': '✅'
        }
    except Exception as e:
        return {
            'name': name,
            'return_pct': 0,
            'final_balance': initial_balance,
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'sharpe': 0,
            'sortino': 0,
            'max_dd_pct': 0,
            'avg_trade': 0,
            'largest_profit': 0,
            'largest_loss': 0,
            'max_consec_wins': 0,
            'max_consec_losses': 0,
            'avg_duration_min': 0,
            'net_profit': 0,
            'status': f'❌ {str(e)[:50]}'
        }


def main():
    print("=" * 70)
    print("📊 3-MONTH XAU/USD STRATEGY COMPARISON BACKTEST")
    print("=" * 70)
    
    # Load data — prefer M15 for more signal frequency, fallback to H1
    data_path = "data/xauusd_1mo_m15.csv"
    if not Path(data_path).exists():
        data_path = "data/xauusd_3mo_h1.csv"
    
    print(f"\n📂 Loading data from {data_path}...")
    data = load_data(data_path)
    print(f"   Candles: {len(data)}")
    print(f"   Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
    
    # Fix timestamps if they're milliseconds in far future (yfinance issue)
    if 'timestamp' in data.columns and data['timestamp'].iloc[0] > 1e12:
        # Ensure they're valid — if year > 2100 then divide
        test_ts = data['timestamp'].iloc[0]
        from datetime import datetime as dt
        try:
            test_date = dt.fromtimestamp(test_ts / 1000)
            if test_date.year > 2100:
                data['timestamp'] = data['timestamp'] // 1000  # fix overflow
        except:
            pass
    
    initial_balance = 10000
    leverage = 200
    
    # Define all strategies with configs
    strategies = [
        ("XAU Hedging", XAUHedgingStrategy(XAUHedgingConfig(
            lots=0.05, stop_loss=600, take_profit=1500,
            trail_start=100, trailing=50, use_session_filter=False
        ))),
        ("XAU Hedging (Session)", XAUHedgingStrategy(XAUHedgingConfig(
            lots=0.05, stop_loss=600, take_profit=1500,
            trail_start=100, trailing=50, use_session_filter=True
        ))),
        ("HFT Scalping", HFTStrategy(HFTConfig(
            lots=0.05, max_spread_pips=50,
            profit_target_pips=20, stop_loss_pips=15,
            momentum_lookback=5, max_hold_seconds=7200
        ))),
        ("7 Candle Breakout", SevenCandleStrategy(SevenCandleConfig(
            lots=0.05, candle_count=5, min_match_pct=0.8,
            use_atr_stops=True, atr_multiplier_sl=1.5, atr_multiplier_tp=2.5
        ))),
        ("ZeroLag EMA", ZeroLagStrategy(ZeroLagConfig(
            lots=0.02, band_length=63, band_multiplier=1.1,
            tp_pips=30, sl_pips=100, max_layers=3,
            lot_multiplier=1.5, use_session_filter=False
        ))),
        ("ZeroLag (Session)", ZeroLagStrategy(ZeroLagConfig(
            lots=0.02, band_length=63, band_multiplier=1.1,
            tp_pips=30, sl_pips=100, max_layers=3,
            lot_multiplier=1.5, use_session_filter=True
        ))),
        ("AI Strategy (ML)", AIStrategy(AIStrategyConfig(
            lots=0.05, min_training_samples=50,
            retrain_interval=30, confidence_threshold=0.55,
            atr_sl_multiplier=1.5, atr_tp_multiplier=2.5
        ))),
        ("BB+MACD+RSI", BBMacdRsiStrategy(BBMacdRsiConfig(
            lots=0.05, rsi_overbought=60, rsi_oversold=40,
            atr_sl_multiplier=2.0, atr_tp_multiplier=3.0
        ))),
        ("Scalping", ScalpingStrategy(ScalpingConfig(
            lots=0.05, lookback=3, momentum_threshold=0.001,
            profit_target_pips=15, stop_loss_pips=10
        ))),
    ]
    
    # Run all backtests
    results = []
    for name, strategy in strategies:
        print(f"\n🔄 Running {name}...")
        result = run_strategy_backtest(name, strategy, data, initial_balance, leverage)
        results.append(result)
        
        if result['total_trades'] > 0:
            emoji = "🟢" if result['return_pct'] > 0 else "🔴"
            print(f"   {emoji} Return: {result['return_pct']:+.2f}% | "
                  f"Trades: {result['total_trades']} | "
                  f"Win Rate: {result['win_rate']:.1f}% | "
                  f"PF: {result['profit_factor']:.2f} | "
                  f"Max DD: {result['max_dd_pct']:.1f}%")
        else:
            print(f"   ⚠️ No trades executed | Status: {result['status']}")
    
    # Sort by return
    results.sort(key=lambda x: x['return_pct'], reverse=True)
    
    # Print ranked table
    print("\n" + "=" * 70)
    print("🏆 STRATEGY RANKING (sorted by return)")
    print("=" * 70)
    print(f"{'#':>2} {'Strategy':<25} {'Return':>10} {'Trades':>7} {'WinRate':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD':>7}")
    print("-" * 70)
    
    for i, r in enumerate(results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        sign = "+" if r['return_pct'] > 0 else ""
        pf_str = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 100 else "∞"
        print(f"{medal}{i:>1} {r['name']:<25} {sign}{r['return_pct']:>8.2f}% {r['total_trades']:>7} "
              f"{r['win_rate']:>7.1f}% {pf_str:>6} {r['sharpe']:>7.2f} {r['max_dd_pct']:>6.1f}%")
    
    print("=" * 70)
    print(f"\n📋 Config: ${initial_balance:,} initial | 1:{leverage} leverage | $0.30 spread | H1 timeframe")
    print(f"📅 Data: {len(data)} candles (~3 months of H1)")
    
    # Print detailed top 3
    print("\n" + "=" * 70)
    print("📊 TOP 3 DETAILED BREAKDOWN")
    print("=" * 70)
    
    for i, r in enumerate(results[:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        print(f"\n{medal} #{i} {r['name']}")
        print(f"   Return:         {r['return_pct']:+.2f}% (${r['net_profit']:+,.2f})")
        print(f"   Final Balance:  ${r['final_balance']:,.2f}")
        print(f"   Total Trades:   {r['total_trades']}")
        print(f"   Win Rate:       {r['win_rate']:.1f}%")
        print(f"   Profit Factor:  {r['profit_factor']:.2f}")
        print(f"   Sharpe Ratio:   {r['sharpe']:.2f}")
        print(f"   Sortino Ratio:  {r['sortino']:.2f}")
        print(f"   Max Drawdown:   {r['max_dd_pct']:.2f}%")
        print(f"   Avg Trade P&L:  ${r['avg_trade']:,.2f}")
        print(f"   Largest Win:    ${r['largest_profit']:,.2f}")
        print(f"   Largest Loss:   ${r['largest_loss']:,.2f}")
        print(f"   Max Consec W/L: {r['max_consec_wins']}/{r['max_consec_losses']}")
    
    # Save results
    results_df = pd.DataFrame(results)
    output_path = "data/backtest_3mo_results.csv"
    results_df.to_csv(output_path, index=False)
    print(f"\n💾 Results saved to {output_path}")
    
    return results


if __name__ == "__main__":
    main()
