"""
Reporter — build Telegram message dari health report + improvements.
"""
import os, json, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(msg: str):
    """Send message via Telegram Bot API."""
    import urllib.request, urllib.parse
    if not BOT_TOKEN or not CHAT_ID or BOT_TOKEN.startswith("token"):
        print(f"[reporter] TG not configured. Message:\n{msg}\n")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }).encode()
    req = urllib.request.Request(url, data=data)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"[reporter] Telegram error: {e}")
        return False


def build_report(health: dict, improvements: list) -> str:
    ts   = health.get("timestamp", "")[:16].replace("T", " ")
    overall = health.get("overall", "?")
    emoji = {"OK": "✅", "WARN": "⚠️", "DEGRADED": "🚨"}.get(overall, "❓")

    lines = [
        f"{emoji} *HFT Bot — Daily Health Check*",
        f"_{ts} UTC_\n",
        f"Overall: *{overall}*",
        f"Best preset: `{health.get('best_preset', '?')}`\n",
        "*Presets:*",
    ]

    status_emoji = {"OK": "✅", "WARN": "⚠️", "DEGRADED": "🚨"}
    for r in health.get("results", []):
        se = status_emoji.get(r["status"], "❓")
        flags = f" [{', '.join(r['flags'])}]" if r["flags"] else ""
        lines.append(
            f"{se} `{r['name']}`: {r['return_pct']:+.1f}% | "
            f"{r['trades']}T | Sharpe {r['sharpe']} | DD {r['max_dd']}%{flags}"
        )

    if improvements:
        lines.append("\n*🔧 Auto-improvements found:*")
        for imp in improvements:
            p = imp["new_params"]
            lines.append(
                f"• `{imp['preset']}`: Sharpe +{imp['improvement']} → "
                f"{p['return_pct']:+.1f}% | DD {p['max_dd']}%"
            )
    else:
        lines.append("\n_No improvements needed._")

    lines.append(f"\n_Next check in 24h_")
    return "\n".join(lines)


def run_report():
    health = {}
    improvements = []

    if os.path.exists("data/health_report.json"):
        with open("data/health_report.json") as f:
            health = json.load(f)
    else:
        print("[reporter] No health report found.")
        return

    if os.path.exists("data/improvements.json"):
        with open("data/improvements.json") as f:
            improvements = json.load(f)

    msg = build_report(health, improvements)
    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    run_report()
