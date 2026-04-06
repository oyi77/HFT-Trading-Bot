"""
Improver — kalau preset DEGRADED, auto-tune parameter dan cari config lebih baik.
Hanya tuning parameter; tidak menulis ulang logika strategi.
"""
import sys, os, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd

from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.strategy.multi_factor import MultiFactorStrategy, MultiFactorConfig
from trading_bot.strategy.smc_scalper import SMCScalperStrategy, SMCScalperConfig


def _clean(df):
    if hasattr(df.columns, 'droplevel') and df.columns.nlevels > 1:
        df.columns = df.columns.droplevel(1)
    df = df.copy()
    df['timestamp'] = df.index.view('int64') // 10**9
    return df


def tune_multi_factor(data, base_config: dict, n_trials=60) -> dict:
    """Grid-search around base_config to find better params."""
    import itertools

    th_range  = [base_config.get('entry_threshold', 0.5) + d for d in [-0.1, 0, 0.1]]
    sl_range  = [base_config.get('atr_sl_multiplier', 3.0) + d for d in [-0.5, 0, 0.5]]
    tp_range  = [base_config.get('atr_tp_multiplier', 5.0) + d for d in [-1.0, 0, 1.0]]
    cd_range  = [base_config.get('cooldown_bars', 12) + d for d in [-4, 0, 4]]

    best = None
    best_sharpe = -99

    for th, sl, tp, cd in itertools.product(th_range, sl_range, tp_range, cd_range):
        if tp <= sl or th <= 0 or th >= 1 or sl <= 0 or tp <= 0 or cd < 2:
            continue
        cfg = MultiFactorConfig(
            lots=0.05, entry_threshold=round(th, 2),
            atr_sl_multiplier=round(sl, 1),
            atr_tp_multiplier=round(tp, 1),
            cooldown_bars=int(cd), min_bars=60,
        )
        e = BacktestEngine(initial_balance=10000, leverage=200, spread=0.30)
        r = e.run(MultiFactorStrategy(cfg), data, symbol='XAUUSD')
        if r.total_trades >= 5 and r.net_profit > 0 and r.sharpe_ratio > best_sharpe:
            best_sharpe = r.sharpe_ratio
            best = {
                "entry_threshold": round(th, 2),
                "atr_sl_multiplier": round(sl, 1),
                "atr_tp_multiplier": round(tp, 1),
                "cooldown_bars": int(cd),
                "return_pct": round(r.total_return_pct, 2),
                "trades": r.total_trades,
                "sharpe": round(r.sharpe_ratio, 2),
                "max_dd": round(r.max_drawdown_pct, 1),
                "net_profit": round(r.net_profit, 2),
            }

    return best or {}


def run_improvements(health_report: dict) -> list:
    """For each DEGRADED preset, try to find better params."""
    degraded = [r for r in health_report['results'] if r['status'] == 'DEGRADED']
    if not degraded:
        print("[improver] No degraded presets. Nothing to tune.")
        return []

    print(f"[improver] {len(degraded)} degraded preset(s). Tuning…")

    m15 = _clean(yf.download('GC=F', period='30d', interval='15m', progress=False))
    h1  = _clean(yf.download('GC=F', period='60d', interval='1h',  progress=False))

    improvements = []
    for preset in degraded:
        name = preset['name']
        print(f"[improver] Tuning {name}…")

        # Pick data based on preset name
        data = h1 if 'h1' in name else m15

        if 'mf_' in name:
            # Base from current best
            base = {"entry_threshold": 0.50, "atr_sl_multiplier": 3.0,
                    "atr_tp_multiplier": 5.0, "cooldown_bars": 12}
            result = tune_multi_factor(data, base)
            if result:
                improvements.append({
                    "preset": name,
                    "new_params": result,
                    "improvement": round(result['sharpe'] - preset['sharpe'], 2),
                })
                print(f"  ✅ Found better: Sharpe {preset['sharpe']} → {result['sharpe']} | "
                      f"Return {result['return_pct']:+.1f}% | DD {result['max_dd']:.1f}%")
            else:
                print(f"  ⚠️ No improvement found for {name}")
        else:
            print(f"  [improver] Skipping {name} (no auto-tuner for this strategy type)")

    # Save improvements
    os.makedirs("data", exist_ok=True)
    with open("data/improvements.json", "w") as f:
        json.dump(improvements, f, indent=2)

    return improvements


if __name__ == "__main__":
    with open("data/health_report.json") as f:
        report = json.load(f)
    imps = run_improvements(report)
    print(f"\n[improver] Done. {len(imps)} improvement(s) found.")
