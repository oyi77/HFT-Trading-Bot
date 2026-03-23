#!/usr/bin/env python3
"""
Scalping Strategy Sweep — Test all strategies across M5/M15/H1 with parameter variations.
Focus: find profitable scalping configs for fast profit.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from trading_bot.core.backtest_engine import BacktestEngine

# Strategy imports
from trading_bot.strategy.ai_strategy import AIStrategy, AIStrategyConfig
from trading_bot.strategy.smc_scalper import SMCScalperStrategy, SMCScalperConfig
from trading_bot.strategy.mean_reversion_scalper import MeanReversionScalper, MeanReversionConfig
from trading_bot.strategy.regime_scalper import RegimeScalperStrategy, RegimeScalperConfig
from trading_bot.strategy.bb_macd_rsi import BBMacdRsiStrategy, BBMacdRsiConfig
from trading_bot.strategy.scalping import ScalpingStrategy, ScalpingConfig
from trading_bot.strategy.hft import HFTStrategy, HFTConfig

def generate_configs():
    """Generate all strategy configs to test."""
    configs = []

    # === AI Strategy (tuned for scalping on M15) ===
    for conf_thresh in [0.45, 0.50, 0.55]:
        for atr_sl in [1.0, 1.5, 2.0]:
            for atr_tp in [1.5, 2.0, 2.5, 3.0]:
                if atr_tp <= atr_sl:
                    continue
                for retrain in [10, 15, 20]:
                    cfg = AIStrategyConfig(
                        lots=0.05, max_positions=2,
                        min_training_samples=30,
                        retrain_interval=retrain,
                        confidence_threshold=conf_thresh,
                        atr_sl_multiplier=atr_sl,
                        atr_tp_multiplier=atr_tp,
                        lookahead_bars=5,
                    )
                    configs.append(("AI_Scalp", AIStrategy(cfg), cfg))

    # === SMC Scalper ===
    for atr_sl in [1.0, 1.5, 2.0]:
        for atr_tp in [1.5, 2.0, 2.5, 3.0]:
            if atr_tp <= atr_sl:
                continue
            for ob_strength in [0.2, 0.3, 0.4]:
                cfg = SMCScalperConfig(
                    lots=0.05, max_positions=2,
                    atr_sl_multiplier=atr_sl,
                    atr_tp_multiplier=atr_tp,
                    ob_strength_min=ob_strength,
                    min_bars=40,
                )
                configs.append(("SMC_Scalp", SMCScalperStrategy(cfg), cfg))

    # === Mean Reversion Scalper ===
    for bb_std in [1.8, 2.0, 2.2, 2.5]:
        for rsi_ob in [70, 75, 80]:
            for atr_sl in [0.8, 1.0, 1.2, 1.5]:
                for atr_tp in [1.2, 1.5, 1.8, 2.0]:
                    if atr_tp <= atr_sl:
                        continue
                    rsi_os = 100 - rsi_ob
                    cfg = MeanReversionConfig(
                        lots=0.05, max_positions=2,
                        bb_std_entry=bb_std,
                        bb_std_extreme=bb_std + 0.5,
                        rsi_ob=rsi_ob, rsi_os=rsi_os,
                        atr_sl_multiplier=atr_sl,
                        atr_tp_multiplier=atr_tp,
                        vwap_zscore_threshold=1.5,
                        min_bars=40,
                    )
                    configs.append(("MeanRev", MeanReversionScalper(cfg), cfg))

    # === Regime Scalper ===
    for trend_tp in [2.0, 2.5, 3.0]:
        for range_tp in [1.2, 1.5, 2.0]:
            for adx_trend in [20, 25, 30]:
                cfg = RegimeScalperConfig(
                    lots=0.05, max_positions=2,
                    trend_atr_tp=trend_tp,
                    range_atr_tp=range_tp,
                    adx_trend_threshold=adx_trend,
                    adx_range_threshold=adx_trend - 7,
                    volatile_skip=False,
                    min_bars=60,
                )
                configs.append(("Regime", RegimeScalperStrategy(cfg), cfg))

    # === AI on H1 (baseline comparison) ===
    for conf in [0.50, 0.55, 0.60]:
        for atr_sl in [2.5, 3.0, 3.5]:
            for atr_tp in [3.5, 4.0, 5.0]:
                if atr_tp <= atr_sl:
                    continue
                cfg = AIStrategyConfig(
                    lots=0.05, max_positions=2,
                    min_training_samples=50,
                    retrain_interval=20,
                    confidence_threshold=conf,
                    atr_sl_multiplier=atr_sl,
                    atr_tp_multiplier=atr_tp,
                    lookahead_bars=10,
                )
                configs.append(("AI_H1", AIStrategy(cfg), cfg))

    return configs


def run_sweep():
    # Load all timeframe data
    datasets = {}
    for label, filename in [
        ("M5", "data/xauusd_2mo_m5.csv"),
        ("M15", "data/xauusd_2mo_m15.csv"),
        ("H1", "data/xauusd_3mo_h1.csv"),
    ]:
        if os.path.exists(filename):
            df = pd.read_csv(filename)
            datasets[label] = df
            print(f"  {label}: {len(df)} bars")
        else:
            print(f"  {label}: MISSING ({filename})")

    configs = generate_configs()
    print(f"\n🔬 Testing {len(configs)} configurations...\n")

    results = []
    tested = 0

    for strat_name, strategy, cfg in configs:
        # Route to appropriate timeframe
        if strat_name == "AI_H1":
            tf_label = "H1"
        elif strat_name in ("AI_Scalp", "MeanRev", "SMC_Scalp", "Regime"):
            tf_label = "M15"  # Primary scalping timeframe
        else:
            tf_label = "M15"

        if tf_label not in datasets:
            continue

        data = datasets[tf_label]
        engine = BacktestEngine(initial_balance=10000, leverage=200, spread=0.30)

        try:
            r = engine.run(strategy, data, symbol='XAUUSD')
            tested += 1

            if r.total_trades >= 3:
                # Extract key config params
                params = {}
                if hasattr(cfg, 'atr_sl_multiplier'):
                    params['sl'] = cfg.atr_sl_multiplier
                if hasattr(cfg, 'atr_tp_multiplier'):
                    params['tp'] = cfg.atr_tp_multiplier
                if hasattr(cfg, 'confidence_threshold'):
                    params['conf'] = cfg.confidence_threshold
                if hasattr(cfg, 'bb_std_entry'):
                    params['bb'] = cfg.bb_std_entry
                if hasattr(cfg, 'rsi_ob'):
                    params['rsi_ob'] = cfg.rsi_ob
                if hasattr(cfg, 'adx_trend_threshold'):
                    params['adx'] = cfg.adx_trend_threshold
                if hasattr(cfg, 'trend_atr_tp'):
                    params['trend_tp'] = cfg.trend_atr_tp
                if hasattr(cfg, 'range_atr_tp'):
                    params['range_tp'] = cfg.range_atr_tp

                results.append({
                    'strategy': strat_name,
                    'timeframe': tf_label,
                    'params': str(params),
                    'return_pct': r.total_return_pct,
                    'trades': r.total_trades,
                    'win_rate': r.win_rate,
                    'profit_factor': r.profit_factor,
                    'sharpe': r.sharpe_ratio,
                    'max_dd': r.max_drawdown_pct,
                    'net_profit': r.net_profit,
                })

            if tested % 50 == 0:
                profitable = sum(1 for r in results if r['net_profit'] > 0)
                print(f"  ... {tested} tested, {len(results)} with 3+ trades, {profitable} profitable", flush=True)

        except Exception as e:
            tested += 1

    # Sort and display
    results.sort(key=lambda x: x['net_profit'], reverse=True)
    profitable = [r for r in results if r['net_profit'] > 0]

    print(f"\n{'='*100}")
    print(f"SCALPING SWEEP COMPLETE — {tested} configs tested, {len(results)} with 3+ trades")
    print(f"Profitable: {len(profitable)}/{len(results)} ({len(profitable)/max(len(results),1)*100:.0f}%)")
    print(f"{'='*100}\n")

    # Top 25 by profit
    print(f"{'#':>2} {'Strategy':>12} {'TF':>3} {'Return':>8} {'Trades':>6} {'WR':>6} {'PF':>6} {'Sharpe':>7} {'DD':>6} {'Profit':>10}")
    print('-' * 90)
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    for i, r in enumerate(results[:25], 1):
        m = medals.get(i, '  ')
        pf = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 100 else '∞'
        print(f"{m}{i:>1} {r['strategy']:>12} {r['timeframe']:>3} {r['return_pct']:>+7.1f}% {r['trades']:>6} {r['win_rate']:>5.1f}% {pf:>6} {r['sharpe']:>7.2f} {r['max_dd']:>5.1f}% ${r['net_profit']:>+9,.0f}")

    # Best per strategy
    print(f"\n--- BEST PER STRATEGY ---")
    seen = set()
    for r in results:
        if r['strategy'] not in seen and r['net_profit'] > 0:
            seen.add(r['strategy'])
            pf = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 100 else '∞'
            print(f"  {r['strategy']:>12} ({r['timeframe']}): {r['return_pct']:+.1f}% | {r['trades']} trades | WR={r['win_rate']:.1f}% | PF={pf} | Sharpe={r['sharpe']:.2f} | DD={r['max_dd']:.1f}%")
            print(f"               params: {r['params']}")

    # Best by Sharpe
    print(f"\n--- BEST BY SHARPE (risk-adjusted, profitable only) ---")
    by_sharpe = sorted(profitable, key=lambda x: x['sharpe'], reverse=True)
    for i, r in enumerate(by_sharpe[:5], 1):
        pf = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 100 else '∞'
        print(f"  {i}. {r['strategy']:>12} ({r['timeframe']}): Sharpe={r['sharpe']:.2f} | {r['return_pct']:+.1f}% | DD={r['max_dd']:.1f}%")

    # Best by trade count (active + profitable)
    print(f"\n--- MOST ACTIVE (profitable, most trades) ---")
    by_trades = sorted(profitable, key=lambda x: x['trades'], reverse=True)
    for i, r in enumerate(by_trades[:5], 1):
        print(f"  {i}. {r['strategy']:>12} ({r['timeframe']}): {r['trades']} trades | {r['return_pct']:+.1f}% | WR={r['win_rate']:.1f}%")

    # Save CSV
    df = pd.DataFrame(results)
    df.to_csv('data/scalping_sweep_results.csv', index=False)
    print(f"\nSaved to data/scalping_sweep_results.csv")


if __name__ == "__main__":
    print("🔬 SCALPING STRATEGY SWEEP — Finding Fast Profit Configs\n")
    run_sweep()
