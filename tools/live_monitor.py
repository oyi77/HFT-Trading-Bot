#!/usr/bin/env python3
"""
Live Paper Trading Monitor — SMC Scalper + AI Best
Fetches real-time XAU price, runs strategies, logs signals to file + Telegram.
Run via cron every 15 minutes for M15 strategy.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd

from trading_bot.strategy.smc_scalper import SMCScalperStrategy, SMCScalperConfig
from trading_bot.strategy.ai_strategy import AIStrategy, BEST_XAU_H1

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'monitor_state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'paper_trades.jsonl')
BALANCE_START = 10000.0


def send_telegram(message: str):
    """Send Telegram notification if configured."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        logger.info(f"[TG-SKIP] {message[:80]}...")
        return
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        logger.info("[TG-SENT] Message delivered")
    except Exception as e:
        logger.error(f"[TG-ERR] {e}")


def load_state() -> dict:
    """Load persistent state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        'balance': BALANCE_START,
        'positions': [],
        'trades': [],
        'total_pnl': 0.0,
        'last_signal_time': '',
        'smc_tick_count': 0,
    }


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)


def log_trade(trade: dict):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(trade, default=str) + '\n')


def check_exits(state: dict, current_price: float):
    """Check SL/TP for open positions."""
    closed = []
    for pos in state['positions']:
        pnl = 0
        reason = ''
        if pos['side'] == 'buy':
            if current_price <= pos['sl']:
                pnl = (pos['sl'] - pos['entry_price']) * pos['lots'] * 100
                reason = 'SL'
            elif current_price >= pos['tp']:
                pnl = (pos['tp'] - pos['entry_price']) * pos['lots'] * 100
                reason = 'TP'
        else:  # sell
            if current_price >= pos['sl']:
                pnl = (pos['entry_price'] - pos['sl']) * pos['lots'] * 100
                reason = 'SL'
            elif current_price <= pos['tp']:
                pnl = (pos['entry_price'] - pos['tp']) * pos['lots'] * 100
                reason = 'TP'

        if reason:
            trade = {
                'time_close': datetime.now(timezone.utc).isoformat(),
                'time_open': pos['time'],
                'side': pos['side'],
                'entry': pos['entry_price'],
                'exit': pos['sl'] if reason == 'SL' else pos['tp'],
                'pnl': round(pnl, 2),
                'reason': reason,
                'strategy': pos['strategy'],
            }
            closed.append(pos)
            state['balance'] += pnl
            state['total_pnl'] += pnl
            state['trades'].append(trade)
            log_trade(trade)

            emoji = '✅' if pnl > 0 else '❌'
            msg = (
                f"{emoji} *TRADE CLOSED — {reason}*\n"
                f"Strategy: `{pos['strategy']}`\n"
                f"Side: {pos['side'].upper()}\n"
                f"Entry: ${pos['entry_price']:,.2f} → Exit: ${trade['exit']:,.2f}\n"
                f"P&L: ${pnl:+,.2f}\n"
                f"Balance: ${state['balance']:,.2f} ({state['total_pnl']:+,.2f} total)"
            )
            send_telegram(msg)
            logger.info(f"CLOSED {pos['side']} {reason} PnL=${pnl:+.2f}")

    for pos in closed:
        state['positions'].remove(pos)


def run():
    state = load_state()
    now = datetime.now(timezone.utc)

    # Fetch latest M15 data (7 days for warmup)
    try:
        data = yf.download("GC=F", period="7d", interval="15m", progress=False)
        if hasattr(data.columns, 'droplevel') and data.columns.nlevels > 1:
            data.columns = data.columns.droplevel(1)
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        return

    if len(data) < 50:
        logger.warning(f"Not enough data: {len(data)} bars")
        return

    current_price = float(data['Close'].iloc[-1])
    current_high = float(data['High'].iloc[-1])
    current_low = float(data['Low'].iloc[-1])
    latest_time = str(data.index[-1])

    logger.info(f"XAU=${current_price:,.2f} | Bars={len(data)} | Latest={latest_time}")

    # Check exits first
    check_exits(state, current_price)

    # Initialize SMC strategy and warm it up
    smc_cfg = SMCScalperConfig(
        lots=0.05, max_positions=2,
        atr_sl_multiplier=1.5, atr_tp_multiplier=3.0,
        ob_strength_min=0.2, min_bars=30,
    )
    smc = SMCScalperStrategy(smc_cfg)

    # Feed all bars to warm up strategy state
    last_signal = None
    for i, row in data.iterrows():
        sig = smc.on_tick(float(row['Close']), float(row['Low']), float(row['High']), state['positions'], 0)
        if sig:
            last_signal = sig
            last_signal['_time'] = str(i)

    # Only act on the very last bar's signal (current)
    # Check if we already signaled this bar
    if last_signal and last_signal.get('_time') == latest_time:
        if state['last_signal_time'] != latest_time:
            # New signal!
            open_count = len(state['positions'])
            if open_count < 2:
                pos = {
                    'side': last_signal['side'],
                    'entry_price': current_price,
                    'sl': last_signal['sl'],
                    'tp': last_signal['tp'],
                    'lots': last_signal['amount'],
                    'time': now.isoformat(),
                    'strategy': 'smc_best',
                }
                state['positions'].append(pos)
                state['last_signal_time'] = latest_time

                sl_dist = abs(current_price - last_signal['sl'])
                tp_dist = abs(current_price - last_signal['tp'])

                msg = (
                    f"🔔 *NEW SIGNAL — SMC Scalper*\n"
                    f"Side: *{last_signal['side'].upper()}*\n"
                    f"Price: ${current_price:,.2f}\n"
                    f"SL: ${last_signal['sl']:,.2f} (-${sl_dist:,.2f})\n"
                    f"TP: ${last_signal['tp']:,.2f} (+${tp_dist:,.2f})\n"
                    f"Trend: {'BULLISH' if smc.trend == 1 else 'BEARISH'}\n"
                    f"Reason: {last_signal.get('reason', 'SMC')}\n"
                    f"Open positions: {open_count + 1}/2\n"
                    f"Balance: ${state['balance']:,.2f}"
                )
                send_telegram(msg)
                logger.info(f"SIGNAL: {last_signal['side'].upper()} at ${current_price:,.2f}")
                log_trade({'type': 'signal', 'time': now.isoformat(), **last_signal, 'price': current_price})
            else:
                logger.info("Signal blocked: max positions reached")
    else:
        logger.info(f"No new signal on latest bar. Trend: {'BULL' if smc.trend==1 else 'BEAR' if smc.trend==-1 else 'FLAT'}")

    # Status summary
    logger.info(f"Balance: ${state['balance']:,.2f} | PnL: ${state['total_pnl']:+,.2f} | Open: {len(state['positions'])} | Trades: {len(state['trades'])}")

    save_state(state)


if __name__ == '__main__':
    run()
