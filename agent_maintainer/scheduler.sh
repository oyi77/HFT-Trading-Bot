#!/usr/bin/env bash
# scheduler.sh — entry point for cron
# Cron entry (run daily at 07:00 WIB / 00:00 UTC):
#   0 0 * * * /tmp/HFT-Trading-Bot/agent_maintainer/scheduler.sh >> /tmp/HFT-Trading-Bot/data/agent.log 2>&1

set -e
REPO="/tmp/HFT-Trading-Bot"

# 1. Pull latest code
cd "$REPO"
git pull origin master --ff-only 2>&1 || echo "[scheduler] git pull failed, continuing with local"

# 2. Install deps if needed
pip install -q yfinance pandas 2>/dev/null

# 3. Run the agent
python3 "$REPO/agent_maintainer/agent.py"
