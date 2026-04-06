"""
Health Check — forward-test semua preset, detect degradation, return report dict.
"""
import warnings, sys, os, json
from datetime import datetime, timezone
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from agent_maintainer.data_store import DataStore
from trading_bot.core.backtest_engine import BacktestEngine
from trading_bot.strategy.multi_factor import (
    MultiFactorStrategy,
    MF_M15_ULTRA, MF_M15_ULTRA_FAST, MF_H1_SAFE, MF_H1_BEST,
)
from trading_bot.strategy.smc_scalper import SMCScalperStrategy, SMCScalperConfig
from trading_bot.strategy.ai_strategy import AIStrategy, BEST_XAU_H1

# ── thresholds for degradation alert ──────────────────────────────────────────
THRESHOLDS = {
    "min_return_pct": -5.0,    # below → degraded
    "max_dd_pct":      20.0,   # above → degraded
    "min_sharpe":       0.5,   # below → degraded
    "min_trades":       3,     # below → not enough signal
}


def fetch_data():
    """Fetch latest M15 and H1 data. Returns (m15, h1) DataFrames."""
    def _clean(df):
        if hasattr(df.columns, 'droplevel') and df.columns.nlevels > 1:
            df.columns = df.columns.droplevel(1)
        df = df.copy()
        df['timestamp'] = df.index.view('int64') // 10**9
        return df

    m15 = _clean(yf.download('GC=F', period='30d', interval='15m', progress=False))
    h1  = _clean(yf.download('GC=F', period='60d', interval='1h',  progress=False))
    return m15, h1


def run_preset(name, strategy, data, balance=10000):
    e = BacktestEngine(initial_balance=balance, leverage=200, spread=0.30)
    r = e.run(strategy, data, symbol='XAUUSD')
    status = "OK"
    flags = []
    if r.total_trades < THRESHOLDS["min_trades"]:
        flags.append("LOW_TRADES")
    if r.total_return_pct < THRESHOLDS["min_return_pct"]:
        flags.append("NEGATIVE_RETURN")
        status = "DEGRADED"
    if r.max_drawdown_pct > THRESHOLDS["max_dd_pct"]:
        flags.append("HIGH_DD")
        status = "DEGRADED"
    if r.sharpe_ratio < THRESHOLDS["min_sharpe"] and r.total_trades >= THRESHOLDS["min_trades"]:
        flags.append("LOW_SHARPE")
        status = "WARN"

    return {
        "name": name,
        "status": status,
        "flags": flags,
        "return_pct": round(r.total_return_pct, 2),
        "trades": r.total_trades,
        "win_rate": round(r.win_rate, 1),
        "profit_factor": round(r.profit_factor, 2) if r.profit_factor < 1000 else 99.0,
        "sharpe": round(r.sharpe_ratio, 2),
        "max_dd": round(r.max_drawdown_pct, 1),
        "net_profit": round(r.net_profit, 2),
    }


def run_health_check():
    ds = DataStore()
    print("[agent] Fetching market data via DataStore…")
    m15 = ds.get("M15", days=30)
    h1  = ds.get("H1",  days=60)
    print(f"[agent] M15: {len(m15)} bars | H1: {len(h1)} bars")

    smc_cfg = SMCScalperConfig(lots=0.05, max_positions=2,
        atr_sl_multiplier=1.5, atr_tp_multiplier=3.0,
        ob_strength_min=0.2, min_bars=30)

    presets = [
        ("mf_m15_ultra",      MultiFactorStrategy(MF_M15_ULTRA),      m15),
        ("mf_m15_ultra_fast", MultiFactorStrategy(MF_M15_ULTRA_FAST),  m15),
        ("mf_h1_safe",        MultiFactorStrategy(MF_H1_SAFE),         h1),
        ("mf_h1_best",        MultiFactorStrategy(MF_H1_BEST),         h1),
        ("smc_best",          SMCScalperStrategy(smc_cfg),             m15),
        ("ai_best",           AIStrategy(BEST_XAU_H1),                 h1),
    ]

    results = []
    for name, strategy, data in presets:
        print(f"[agent] Testing {name}…")
        res = run_preset(name, strategy, data)
        results.append(res)
        flag_str = f" ⚠️ {res['flags']}" if res['flags'] else ""
        print(f"  {res['status']:>8} | {res['return_pct']:>+7.1f}% | "
              f"{res['trades']:>3}T | Sharpe={res['sharpe']:.2f} | DD={res['max_dd']:.1f}%{flag_str}")

    degraded = [r for r in results if r['status'] == 'DEGRADED']
    warned   = [r for r in results if r['status'] == 'WARN']
    ok       = [r for r in results if r['status'] == 'OK']

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": "DEGRADED" if degraded else ("WARN" if warned else "OK"),
        "results": results,
        "degraded_count": len(degraded),
        "warn_count": len(warned),
        "ok_count": len(ok),
        "best_preset": max(results, key=lambda x: x['sharpe'])["name"] if results else None,
    }

    # Save to DB for historical tracking
    for r in results:
        tf = "H1" if "h1" in r["name"] else "M15"
        ds.save_forward_result(r["name"], tf, r)

    # Save JSON snapshot
    os.makedirs("data", exist_ok=True)
    out = "data/health_report.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[agent] Report saved → {out}")
    return report


if __name__ == "__main__":
    r = run_health_check()
    print(f"\nOverall: {r['overall']} | Best: {r['best_preset']}")
