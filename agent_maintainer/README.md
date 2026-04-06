# Agent Maintainer

Autonomous agent yang maintain repo `HFT-Trading-Bot` setiap hari.

## Flow
```
[cron 00:00 UTC daily]
        │
        ▼
  health_check.py   ← forward-test semua preset (M15 + H1, 30/60 hari)
        │
        ▼
  improver.py       ← kalau DEGRADED → grid-search parameter baru
        │
        ▼
  agent.py          ← patch multi_factor.py + git commit + push
        │
        ▼
  reporter.py       ← kirim laporan ke Telegram
```

## Preset yang di-monitor

| Preset | TF | Baseline Sharpe | Baseline DD |
|---|---|---|---|
| `mf_m15_ultra` | M15 | 5.96 | 7.7% |
| `mf_m15_ultra_fast` | M15 | 5.46 | 7.7% |
| `mf_h1_safe` | H1 | 2.12 | 13.8% |
| `mf_h1_best` | H1 | 2.37 | 23.1% |
| `smc_best` | M15 | 2.44 | 6.2% |
| `ai_best` | H1 | 0.61 | 21% |

## Degradation thresholds

- Return < -5% → DEGRADED
- Max DD > 20% → DEGRADED
- Sharpe < 0.5 → WARN
- Trades < 3 → LOW_TRADES

## Deploy

```bash
# Setup cron (daily 00:00 UTC = 07:00 WIB)
(crontab -l 2>/dev/null; echo "0 0 * * * cd /tmp/HFT-Trading-Bot && python3 agent_maintainer/agent.py >> data/agent.log 2>&1") | crontab -

# Set Telegram credentials
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Test run
python3 agent_maintainer/agent.py
```

## GitHub Actions (optional)

Copy `.github/workflows/daily_health.yml` for cloud-based scheduling (no server needed).
