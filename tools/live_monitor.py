#!/usr/bin/env python3
"""
Live Paper Trading Monitor — SMC + AI + Multi-Factor (3 strategies)
Fetches real-time XAU price, runs strategies, logs signals + Telegram alerts.
Cron: */15 * * * *
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
from trading_bot.strategy.multi_factor import MultiFactorStrategy, MF_H1_SAFE, MF_M15_ULTRA
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

    # ── STRATEGY 1: SMC Scalper (M15) ──────────────────────────────────
    smc_cfg = SMCScalperConfig(
        lots=0.05, max_positions=2,
        atr_sl_multiplier=1.5, atr_tp_multiplier=3.0,
        ob_strength_min=0.2, min_bars=30,
    )
    smc = SMCScalperStrategy(smc_cfg)

    last_smc_signal = None
    for i, row in data.iterrows():
        sig = smc.on_tick(float(row['Close']), float(row['Low']), float(row['High']), state['positions'], 0)
        if sig:
            last_smc_signal = sig
            last_smc_signal['_time'] = str(i)
            last_smc_signal['_strategy'] = 'smc_best'

    # ── STRATEGY 2: AI Best (H1) ──────────────────────────────────────
    # Fetch H1 data separately
    ai_signal = None
    try:
        h1_data = yf.download("GC=F", period="30d", interval="1h", progress=False)
        if hasattr(h1_data.columns, 'droplevel') and h1_data.columns.nlevels > 1:
            h1_data.columns = h1_data.columns.droplevel(1)
        if len(h1_data) >= 50:
            ai = AIStrategy(BEST_XAU_H1)
            for i, row in h1_data.iterrows():
                sig = ai.on_tick(float(row['Close']), float(row['Low']), float(row['High']), [], 0)
                if sig:
                    ai_signal = sig
                    ai_signal['_time'] = str(i)
                    ai_signal['_strategy'] = 'ai_best'
            h1_latest = str(h1_data.index[-1])
            logger.info(f"AI_H1: {len(h1_data)} bars | Latest={h1_latest} | Signal={'YES' if ai_signal and ai_signal.get('_time')==h1_latest else 'NO'}")
    except Exception as e:
        logger.error(f"H1 data fetch error: {e}")

    # ── STRATEGY 3: Multi-Factor H1 (NEW — best overall) ─────────────
    mf_h1_signal = None
    mf_m15_signal = None
    try:
        h1_for_mf = h1_data if 'h1_data' in dir() and len(h1_data) >= 60 else None
        if h1_for_mf is not None:
            mf_h1 = MultiFactorStrategy(MF_H1_SAFE)
            for i, row in h1_for_mf.iterrows():
                sig = mf_h1.on_tick(float(row['Close']), float(row['Low']), float(row['High']), state['positions'], 0)
                if sig:
                    mf_h1_signal = sig
                    mf_h1_signal['_time'] = str(i)
                    mf_h1_signal['_strategy'] = 'mf_h1_safe'
            logger.info(f"MF_H1: Signal={'YES' if mf_h1_signal and mf_h1_signal.get('_time')==str(h1_for_mf.index[-1]) else 'NO'}")

        # Multi-Factor M15
        mf_m15 = MultiFactorStrategy(MF_M15_ULTRA)
        for i, row in data.iterrows():
            sig = mf_m15.on_tick(float(row['Close']), float(row['Low']), float(row['High']), state['positions'], 0)
            if sig:
                mf_m15_signal = sig
                mf_m15_signal['_time'] = str(i)
                mf_m15_signal['_strategy'] = 'mf_m15_ultra'
        logger.info(f"MF_M15: Signal={'YES' if mf_m15_signal and mf_m15_signal.get('_time')==latest_time else 'NO'}")
    except Exception as e:
        logger.error(f"MF strategy error: {e}")

    # ── PROCESS SIGNALS ────────────────────────────────────────────────
    all_signals = []
    if last_smc_signal and last_smc_signal.get('_time') == latest_time:
        all_signals.append(last_smc_signal)
    if ai_signal and 'h1_data' in dir() and len(h1_data) > 0 and ai_signal.get('_time') == str(h1_data.index[-1]):
        all_signals.append(ai_signal)
    if mf_h1_signal and 'h1_data' in dir() and len(h1_data) > 0 and mf_h1_signal.get('_time') == str(h1_data.index[-1]):
        all_signals.append(mf_h1_signal)
    if mf_m15_signal and mf_m15_signal.get('_time') == latest_time:
        all_signals.append(mf_m15_signal)

    for signal in all_signals:
        strat_name = signal.get('_strategy', 'unknown')
        signal_time = signal.get('_time', '')

        # Check if already signaled this bar for this strategy
        last_key = f'last_signal_{strat_name}'
        if state.get(last_key) == signal_time:
            continue

        open_count = len(state['positions'])
        max_pos = 8  # 2 per strategy × 4 strategies
        strat_positions = sum(1 for p in state['positions'] if p.get('strategy') == strat_name)

        if open_count >= max_pos or strat_positions >= 2:
            logger.info(f"[{strat_name}] Signal blocked: positions full ({strat_positions}/2, total {open_count}/{max_pos})")
            continue

        pos = {
            'side': signal['side'],
            'entry_price': current_price,
            'sl': signal['sl'],
            'tp': signal['tp'],
            'lots': signal['amount'],
            'time': now.isoformat(),
            'strategy': strat_name,
        }
        state['positions'].append(pos)
        state[last_key] = signal_time

        sl_dist = abs(current_price - signal['sl'])
        tp_dist = abs(current_price - signal['tp'])
        trend_label = ''
        if strat_name == 'smc_best':
            trend_label = 'BULLISH' if smc.trend == 1 else 'BEARISH'
        elif 'mf_' in strat_name:
            trend_label = 'Multi-Factor'
        else:
            trend_label = 'AI-ML'

        emoji_map = {'smc_best': '🟢', 'ai_best': '🔵', 'mf_h1_safe': '🟡', 'mf_m15_ultra': '🟠'}
        emoji = emoji_map.get(strat_name, '⚪')
        msg = (
            f"{emoji} *NEW SIGNAL — {strat_name.upper()}*\n"
            f"Side: *{signal['side'].upper()}*\n"
            f"Price: ${current_price:,.2f}\n"
            f"SL: ${signal['sl']:,.2f} (-${sl_dist:,.2f})\n"
            f"TP: ${signal['tp']:,.2f} (+${tp_dist:,.2f})\n"
            f"Trend: {trend_label}\n"
            f"Reason: {signal.get('reason', strat_name)}\n"
            f"Positions: {strat_name}={strat_positions+1}/2, total={open_count+1}/{max_pos}\n"
            f"Balance: ${state['balance']:,.2f}"
        )
        send_telegram(msg)
        logger.info(f"[{strat_name}] SIGNAL: {signal['side'].upper()} at ${current_price:,.2f}")
        log_trade({'type': 'signal', 'time': now.isoformat(), 'strategy': strat_name, **signal, 'price': current_price})

    if not all_signals:
        smc_trend = 'BULL' if smc.trend==1 else 'BEAR' if smc.trend==-1 else 'FLAT'
        logger.info(f"No new signals. SMC trend: {smc_trend}")

    # Status summary
    smc_pos  = sum(1 for p in state['positions'] if p.get('strategy') == 'smc_best')
    ai_pos   = sum(1 for p in state['positions'] if p.get('strategy') == 'ai_best')
    mfh1_pos = sum(1 for p in state['positions'] if p.get('strategy') == 'mf_h1_safe')
    mfm15_pos= sum(1 for p in state['positions'] if p.get('strategy') == 'mf_m15_ultra')
    logger.info(f"Balance: ${state['balance']:,.2f} | PnL: ${state['total_pnl']:+,.2f} | SMC:{smc_pos} AI:{ai_pos} MF_H1:{mfh1_pos} MF_M15:{mfm15_pos} | Trades: {len(state['trades'])}")

    save_state(state)


if __name__ == '__main__':
    run()
