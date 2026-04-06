"""
Agent — orchestrator utama. Jalankan via cron (1x sehari):
  0 7 * * * cd /tmp/HFT-Trading-Bot && python3 agent_maintainer/agent.py >> data/agent.log 2>&1

Flow:
  1. Health check (forward-test semua preset)
  2. Kalau ada degraded preset → auto-tune
  3. Kalau improvement ditemukan → update preset file + commit
  4. Kirim laporan ke Telegram
"""
import sys, os, json, subprocess
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print(f"\n{'='*60}")
print(f"[agent] HFT Maintenance Agent started — {datetime.now().isoformat()}")
print(f"{'='*60}")

# ── Step 1: Health check ───────────────────────────────────────────────────────
from agent_maintainer.health_check import run_health_check
health = run_health_check()

# ── Step 2: Auto-improve if needed ────────────────────────────────────────────
improvements = []
if health["overall"] in ("DEGRADED", "WARN"):
    print(f"\n[agent] Overall status: {health['overall']} → running improver…")
    from agent_maintainer.improver import run_improvements
    improvements = run_improvements(health)

    # If improvements found, patch multi_factor.py presets
    if improvements:
        print(f"\n[agent] Patching presets with {len(improvements)} improvement(s)…")
        mf_path = "trading_bot/strategy/multi_factor.py"

        for imp in improvements:
            p = imp["new_params"]
            preset_name = imp["preset"].upper().replace("-", "_").replace(" ", "_")
            patch_lines = [
                f"\n# AUTO-TUNED by agent — {datetime.now().date()} "
                f"(Sharpe {p['sharpe']}, DD {p['max_dd']}%, Return {p['return_pct']:+.1f}%)\n",
                f"{preset_name}_AUTOTUNED = MultiFactorConfig(\n",
                f"    lots=0.05, max_positions=2,\n",
                f"    entry_threshold={p['entry_threshold']},\n",
                f"    atr_sl_multiplier={p['atr_sl_multiplier']},\n",
                f"    atr_tp_multiplier={p['atr_tp_multiplier']},\n",
                f"    cooldown_bars={p['cooldown_bars']},\n",
                f"    min_bars=60,\n",
                f")\n",
            ]
            with open(mf_path, "a") as f:
                f.writelines(patch_lines)
            print(f"[agent] Patched {preset_name}_AUTOTUNED into {mf_path}")

        # Git commit
        try:
            subprocess.run(["git", "add", "-A"], check=True)
            msg = (
                f"[agent] auto-tune {datetime.now().date()}: "
                f"{len(improvements)} preset(s) improved\n\n"
                + "\n".join(
                    f"- {i['preset']}: Sharpe +{i['improvement']} | "
                    f"Return {i['new_params']['return_pct']:+.1f}%"
                    for i in improvements
                )
            )
            subprocess.run(["git", "commit", "-m", msg], check=True)
            subprocess.run(["git", "push", "origin", "master"], check=True)
            print("[agent] ✅ Committed & pushed to GitHub")
        except subprocess.CalledProcessError as e:
            print(f"[agent] ⚠️ Git error: {e}")
else:
    print(f"\n[agent] All presets healthy ({health['overall']}). No tuning needed.")

# ── Step 3: Report to Telegram ────────────────────────────────────────────────
print("\n[agent] Sending Telegram report…")
from agent_maintainer.reporter import run_report
run_report()

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"[agent] Done — {datetime.now().isoformat()}")
print(f"  Overall : {health['overall']}")
print(f"  Best    : {health['best_preset']}")
print(f"  Improved: {len(improvements)} preset(s)")
print(f"{'='*60}\n")
