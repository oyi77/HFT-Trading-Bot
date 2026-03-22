"""
Strategy Parameter Sweep — find profitable configs across all strategies.
Tests multiple parameter combos on real XAU/USD data, ranks by profit.
"""
import sys, itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.hft import HFTStrategy, HFTConfig
from trading_bot.strategy.seven_candle import SevenCandleStrategy, SevenCandleConfig
from trading_bot.strategy.zerolag import ZeroLagStrategy, ZeroLagConfig
from trading_bot.strategy.ai_strategy import AIStrategy, AIStrategyConfig
from trading_bot.strategy.bb_macd_rsi import BBMacdRsiStrategy, BBMacdRsiConfig
from trading_bot.strategy.scalping import ScalpingStrategy, ScalpingConfig


def load_data(path):
    df = pd.read_csv(path)
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ('open','high','low','close','volume','timestamp'):
            col_map[c] = cl
    df.rename(columns=col_map, inplace=True)
    if 'timestamp' not in df.columns:
        for col in ['datetime','Datetime','Date','date']:
            if col in df.columns:
                df['timestamp'] = pd.to_datetime(df[col]).astype(int) // 10**6
                break
    for col in ['open','high','low','close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=['open','high','low','close'], inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = 100
    return df


def run_one(name, strategy, data, balance=10000, leverage=200):
    engine = BacktestEngine(
        initial_balance=balance, leverage=leverage,
        spread=0.30, commission=0, slippage=0.05
    )
    try:
        r = engine.run(strategy, data, symbol="XAUUSD")
        return {
            'name': name,
            'return_pct': r.total_return_pct,
            'net_profit': r.net_profit,
            'trades': r.total_trades,
            'win_rate': r.win_rate,
            'profit_factor': r.profit_factor,
            'sharpe': r.sharpe_ratio,
            'max_dd': r.max_drawdown_pct,
            'avg_trade': r.avg_trade,
            'max_consec_loss': r.max_consecutive_losses,
            'ok': True
        }
    except Exception as e:
        return {'name': name, 'return_pct': 0, 'net_profit': 0, 'trades': 0,
                'win_rate': 0, 'profit_factor': 0, 'sharpe': 0, 'max_dd': 0,
                'avg_trade': 0, 'max_consec_loss': 0, 'ok': False, 'err': str(e)[:60]}


def main():
    print("=" * 80)
    print("🔬 STRATEGY PARAMETER SWEEP — Finding Profitable Configs")
    print("=" * 80)

    data = load_data("data/xauusd_3mo_h1.csv")
    print(f"Data: {len(data)} H1 bars | ${data['close'].min():.0f}-${data['close'].max():.0f}")

    configs = []

    # ─── XAU Hedging sweep ────────────────────────────────────────────────
    for sl in [200, 400, 600, 1000]:
        for tp in [300, 600, 1000, 1500, 2000]:
            for session in [True, False]:
                for trail in [0, 50, 100]:
                    c = XAUHedgingConfig(
                        lots=0.05, stop_loss=sl, take_profit=tp,
                        trail_start=trail*2 if trail else 0, trailing=trail,
                        use_session_filter=session
                    )
                    label = f"Hedging SL{sl} TP{tp} {'Sess' if session else 'All'} Trail{trail}"
                    configs.append((label, XAUHedgingStrategy(c)))

    # ─── 7 Candle Breakout sweep ──────────────────────────────────────────
    for candles in [5, 7]:
        for atr_sl in [1.0, 1.5, 2.0, 3.0]:
            for atr_tp in [2.0, 3.0, 4.0, 5.0]:
                if atr_tp <= atr_sl:
                    continue
                c = SevenCandleConfig(
                    lots=0.05, candle_count=candles, min_match_pct=0.8,
                    use_atr_stops=True, atr_multiplier_sl=atr_sl, atr_multiplier_tp=atr_tp
                )
                label = f"7Candle C{candles} SL{atr_sl}x TP{atr_tp}x"
                configs.append((label, SevenCandleStrategy(c)))

    # ─── BB+MACD+RSI sweep ────────────────────────────────────────────────
    for rsi_ob in [60, 65, 70]:
        for rsi_os in [30, 35, 40]:
            for atr_sl in [1.5, 2.0, 3.0]:
                for atr_tp in [2.0, 3.0, 4.0]:
                    if atr_tp <= atr_sl:
                        continue
                    c = BBMacdRsiConfig(
                        lots=0.05, rsi_overbought=rsi_ob, rsi_oversold=rsi_os,
                        atr_sl_multiplier=atr_sl, atr_tp_multiplier=atr_tp
                    )
                    label = f"BBMACD OB{rsi_ob} OS{rsi_os} SL{atr_sl}x TP{atr_tp}x"
                    configs.append((label, BBMacdRsiStrategy(c)))

    # ─── Scalping sweep ───────────────────────────────────────────────────
    for lookback in [3, 5, 8]:
        for mom in [0.001, 0.002, 0.005]:
            for pt in [10, 20, 50, 100]:
                for sl in [10, 20, 50]:
                    c = ScalpingConfig(
                        lots=0.05, lookback=lookback, momentum_threshold=mom,
                        profit_target_pips=pt, stop_loss_pips=sl
                    )
                    label = f"Scalp LB{lookback} Mom{mom} PT{pt} SL{sl}"
                    configs.append((label, ScalpingStrategy(c)))

    # ─── HFT sweep ───────────────────────────────────────────────────────
    for pt in [10, 20, 50]:
        for sl in [10, 20, 30]:
            for mom_lb in [5, 10, 20]:
                c = HFTConfig(
                    lots=0.05, max_spread_pips=50,
                    profit_target_pips=pt, stop_loss_pips=sl,
                    momentum_lookback=mom_lb, max_hold_seconds=7200
                )
                label = f"HFT PT{pt} SL{sl} Mom{mom_lb}"
                configs.append((label, HFTStrategy(c)))

    # ─── AI Strategy sweep ────────────────────────────────────────────────
    for conf_thresh in [0.50, 0.55, 0.60]:
        for atr_sl in [1.5, 2.0, 3.0]:
            for atr_tp in [2.0, 3.0, 4.0]:
                if atr_tp <= atr_sl:
                    continue
                c = AIStrategyConfig(
                    lots=0.05, min_training_samples=50,
                    retrain_interval=20, confidence_threshold=conf_thresh,
                    atr_sl_multiplier=atr_sl, atr_tp_multiplier=atr_tp
                )
                label = f"AI Conf{conf_thresh} SL{atr_sl}x TP{atr_tp}x"
                configs.append((label, AIStrategy(c)))

    print(f"\n🔄 Running {len(configs)} configurations...")

    results = []
    for i, (name, strat) in enumerate(configs):
        r = run_one(name, strat, data)
        results.append(r)
        if (i+1) % 50 == 0:
            print(f"   [{i+1}/{len(configs)}] done...")

    # Filter: only configs with >= 3 trades
    active = [r for r in results if r['trades'] >= 3]
    active.sort(key=lambda x: x['net_profit'], reverse=True)

    print(f"\n✅ Completed. {len(active)}/{len(results)} configs had 3+ trades.\n")

    # Print top 20
    print("=" * 100)
    print("🏆 TOP 20 PROFITABLE STRATEGIES (3+ trades, sorted by net profit)")
    print("=" * 100)
    print(f"{'#':>3} {'Strategy':<45} {'Profit':>10} {'Return':>8} {'Trades':>6} {'WinRate':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD':>7} {'MaxLoss':>7}")
    print("-" * 100)

    for i, r in enumerate(active[:20], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        pf = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 100 else "∞"
        print(f"{medal}{i:>1} {r['name']:<45} ${r['net_profit']:>+8,.0f} {r['return_pct']:>+7.1f}% {r['trades']:>6} {r['win_rate']:>7.1f}% {pf:>6} {r['sharpe']:>7.2f} {r['max_dd']:>6.1f}% {r['max_consec_loss']:>7}")

    # Print bottom 5 (worst)
    print("\n" + "-" * 100)
    print("💀 BOTTOM 5 (worst losses)")
    print("-" * 100)
    for r in active[-5:]:
        pf = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 100 else "∞"
        print(f"   {r['name']:<45} ${r['net_profit']:>+8,.0f} {r['return_pct']:>+7.1f}% {r['trades']:>6} {r['win_rate']:>7.1f}% {pf:>6}")

    # Stats
    profitable = [r for r in active if r['net_profit'] > 0]
    print(f"\n📊 Summary: {len(profitable)}/{len(active)} configs profitable ({len(profitable)/max(len(active),1)*100:.0f}%)")
    if profitable:
        print(f"   Best: {profitable[0]['name']} → ${profitable[0]['net_profit']:+,.0f} ({profitable[0]['return_pct']:+.1f}%)")
    if active:
        avg_ret = sum(r['return_pct'] for r in active) / len(active)
        print(f"   Average return: {avg_ret:+.2f}%")

    # Save all results
    pd.DataFrame(results).to_csv("data/strategy_sweep_results.csv", index=False)
    print(f"\n💾 Full results → data/strategy_sweep_results.csv")

    # Print top 3 detailed
    print("\n" + "=" * 80)
    print("📊 TOP 3 — DETAILED CONFIG")
    print("=" * 80)
    for i, r in enumerate(active[:3], 1):
        medal = ["🥇","🥈","🥉"][i-1]
        print(f"\n{medal} #{i} {r['name']}")
        print(f"   Net Profit:     ${r['net_profit']:+,.2f}")
        print(f"   Return:         {r['return_pct']:+.2f}%")
        print(f"   Total Trades:   {r['trades']}")
        print(f"   Win Rate:       {r['win_rate']:.1f}%")
        print(f"   Profit Factor:  {r['profit_factor']:.2f}")
        print(f"   Sharpe:         {r['sharpe']:.2f}")
        print(f"   Max Drawdown:   {r['max_dd']:.2f}%")
        print(f"   Avg Trade:      ${r['avg_trade']:+,.2f}")
        print(f"   Max Consec L:   {r['max_consec_loss']}")


if __name__ == "__main__":
    main()
