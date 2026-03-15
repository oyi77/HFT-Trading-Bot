# OpenClaw Integration Guide

This repository is compatible with **OpenClaw** as a skill. By adding this repository to your OpenClaw environment, you enable the agent to manage your trading bot, run backtests, and optimize strategies directly from the interface.

## How to Register as a Skill

1. Copy the repository URL.
2. In your OpenClaw environment, use the `find-skills` or `/add-skill` command (depending on your OpenClaw version).
3. Provide this repository's link. OpenClaw will automatically detect the `.agents/skills/trading-bot/SKILL.md` file.

## Features Enabled

- **Automated Trading Management**: Start/stop the bot via text commands.
- **Strategy Analysis**: Run backtests and ask OpenClaw to analyze the results for you.
- **Dynamic Optimization**: Use OpenClaw to find the best HFT parameters based on recent market data.

## Important Note
Ensure you have configured your `.env` file with the necessary API keys and environment variables before asking OpenClaw to interact with live or demo accounts.
