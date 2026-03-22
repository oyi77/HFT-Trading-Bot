"""
Telegram Trade Notification Bot
================================
Lightweight async Telegram notifier for HFT-Trading-Bot.

Usage:
    from trading_bot.interface.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier()          # reads env vars automatically
    await notifier.start()

    await notifier.notify_trade_open(
        symbol="XAUUSD", side="BUY", price=2945.50,
        sl=2943.50, tp=2948.00, lot_size=0.05,
        strategy_name="HFT Scalping",
    )
    await notifier.stop()

Environment variables:
    TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
    TELEGRAM_CHAT_ID    — Target chat / channel / group ID
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────── constants ───────────────────────────────────────

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

DIVIDER = "━━━━━━━━━━━━━━"

# Rate-limit: max 20 messages per 60 s (Telegram group limit ~20 msg/min)
RATE_LIMIT_MESSAGES = 20
RATE_LIMIT_WINDOW = 60.0        # seconds
QUEUE_MAX_SIZE = 200
SEND_RETRY_DELAY = 2.0          # seconds between retries
SEND_MAX_RETRIES = 3


# ─────────────────────────── helpers ─────────────────────────────────────────

def _side_emoji(side: str) -> str:
    """Return 🟢 for BUY, 🔴 for SELL."""
    return "🟢" if side.upper() == "BUY" else "🔴"


def _pnl_emoji(pnl: float) -> str:
    return "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"


def _severity_emoji(severity: str) -> str:
    mapping = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🆘"}
    return mapping.get(severity.lower(), "⚠️")


def _mono(value: str) -> str:
    """Wrap value in Telegram monospace (backtick)."""
    return f"`{value}`"


def _pips(delta: float) -> str:
    """Format a pip delta with sign."""
    pips = round(delta * 10, 1)          # 1 pip = 0.1 for Gold (0.01 for FX)
    sign = "+" if pips >= 0 else ""
    return f"{sign}{pips:.0f} pips"


def _rr(entry: float, sl: float, tp: float) -> str:
    """Format risk:reward ratio string."""
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return "N/A"
    ratio = reward / risk
    return f"1:{ratio:.2f}"


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_price(price: float) -> str:
    return f"${price:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


# ─────────────────────────── dataclass ───────────────────────────────────────

@dataclass
class _QueuedMessage:
    text: str
    parse_mode: str = "MarkdownV2"
    added_at: float = field(default_factory=time.monotonic)


# ─────────────────────────── main class ──────────────────────────────────────

class TelegramNotifier:
    """
    Async Telegram notifier with:
      • zero-dependency HTTP via aiohttp
      • token-bucket rate limiting (20 msg / 60 s)
      • async queue for non-blocking fire-and-forget sends
      • graceful console fallback when token is not configured
    """

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        self.token: str = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id: str = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

        self._enabled: bool = bool(self.token and self.chat_id)
        if not self._enabled:
            logger.warning(
                "TelegramNotifier: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. "
                "Messages will be logged to console only."
            )

        # Rate-limit state  (timestamps of recent sends)
        self._send_times: Deque[float] = deque(maxlen=RATE_LIMIT_MESSAGES)

        # Async queue & worker
        self._queue: asyncio.Queue[_QueuedMessage] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        # aiohttp session (lazy, created in start())
        self._session = None

    # ─────────────────── lifecycle ───────────────────────────────────────────

    async def start(self) -> None:
        """Start the background send worker. Call once before using the notifier."""
        if self._running:
            return
        self._running = True

        if self._enabled:
            try:
                import aiohttp  # noqa: F401 — verify available
                import aiohttp as _aiohttp
                self._session = _aiohttp.ClientSession()
            except ImportError:
                logger.error(
                    "aiohttp is not installed. Install with: pip install aiohttp. "
                    "Falling back to console logging."
                )
                self._enabled = False

        self._worker_task = asyncio.create_task(self._send_worker())
        logger.info("TelegramNotifier started (enabled=%s)", self._enabled)

    async def stop(self) -> None:
        """Drain the queue and shut down."""
        self._running = False
        # Sentinel — wake worker so it can exit
        await self._queue.put(_QueuedMessage(text="__STOP__"))
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=10)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
        if self._session:
            await self._session.close()
        logger.info("TelegramNotifier stopped.")

    # ─────────────────── internal send machinery ─────────────────────────────

    async def _send_worker(self) -> None:
        """Background task — drains the queue respecting rate limits."""
        while True:
            msg = await self._queue.get()
            if msg.text == "__STOP__":
                self._queue.task_done()
                break

            await self._rate_wait()

            if self._enabled:
                await self._post_with_retry(msg)
            else:
                self._log_to_console(msg.text)

            self._queue.task_done()

    async def _rate_wait(self) -> None:
        """Block until sending the next message is within rate limits."""
        now = time.monotonic()
        # Purge timestamps outside the window
        while self._send_times and (now - self._send_times[0]) > RATE_LIMIT_WINDOW:
            self._send_times.popleft()

        if len(self._send_times) >= RATE_LIMIT_MESSAGES:
            # Must wait until the oldest send expires
            wait_for = RATE_LIMIT_WINDOW - (now - self._send_times[0]) + 0.05
            if wait_for > 0:
                logger.debug("Rate limit reached — waiting %.1fs", wait_for)
                await asyncio.sleep(wait_for)

        self._send_times.append(time.monotonic())

    async def _post_with_retry(self, msg: _QueuedMessage) -> None:
        url = TELEGRAM_API.format(token=self.token)
        payload = {
            "chat_id": self.chat_id,
            "text": msg.text,
            "parse_mode": msg.parse_mode,
        }
        for attempt in range(1, SEND_MAX_RETRIES + 1):
            try:
                async with self._session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        logger.debug("Telegram message sent OK.")
                        return
                    body = await resp.text()
                    logger.warning(
                        "Telegram API HTTP %s (attempt %d/%d): %s",
                        resp.status, attempt, SEND_MAX_RETRIES, body[:200],
                    )
                    # 429 Too Many Requests — honour retry_after
                    if resp.status == 429:
                        try:
                            data = await resp.json()
                            retry_after = data.get("parameters", {}).get("retry_after", 5)
                        except Exception:
                            retry_after = 5
                        await asyncio.sleep(retry_after)
                    else:
                        await asyncio.sleep(SEND_RETRY_DELAY * attempt)
            except Exception as exc:
                logger.error(
                    "Telegram send error (attempt %d/%d): %s",
                    attempt, SEND_MAX_RETRIES, exc,
                )
                await asyncio.sleep(SEND_RETRY_DELAY * attempt)

        logger.error("Telegram message dropped after %d retries.", SEND_MAX_RETRIES)
        self._log_to_console(msg.text)   # fallback — at least log it

    def _log_to_console(self, text: str) -> None:
        """Print formatted message to console when Telegram is unavailable."""
        border = "=" * 50
        logger.info("\n%s\n[TELEGRAM MSG]\n%s\n%s", border, text, border)

    def _enqueue(self, text: str, parse_mode: str = "MarkdownV2") -> None:
        """Non-blocking: put message on the queue (drop if full)."""
        msg = _QueuedMessage(text=text, parse_mode=parse_mode)
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueFull:
            logger.warning("TelegramNotifier queue full — message dropped.")
            self._log_to_console(text)

    # ─────────────────── MarkdownV2 escape ───────────────────────────────────

    @staticmethod
    def _esc(text: str) -> str:
        """Escape special chars for Telegram MarkdownV2."""
        special = r"\_*[]()~`>#+-=|{}.!"
        return "".join(f"\\{c}" if c in special else c for c in str(text))

    # ─────────────────── public notification methods ─────────────────────────

    async def notify_trade_open(
        self,
        symbol: str,
        side: str,
        price: float,
        sl: float,
        tp: float,
        lot_size: float,
        strategy_name: str,
    ) -> None:
        """
        Send a trade-open alert.

        Example output:
            🟢 BUY XAUUSD
            ━━━━━━━━━━━━━━
            Strategy: HFT Scalping
            Entry:    $2,945.50
            SL:       $2,943.50 (-20 pips)
            TP:       $2,948.00 (+25 pips)
            Lots:     0.05
            R:R:      1:1.25
            ━━━━━━━━━━━━━━
        """
        emoji = _side_emoji(side)
        side_up = side.upper()
        sym = symbol.upper()

        sl_pips = _pips(sl - price)
        tp_pips = _pips(tp - price)
        rr = _rr(price, sl, tp)

        # Build plain text first, then escape for MarkdownV2
        lines = [
            f"{emoji} *{self._esc(side_up)} {self._esc(sym)}*",
            self._esc(DIVIDER),
            f"Strategy: {self._esc(strategy_name)}",
            f"Entry:    `{price:,.2f}`",
            f"SL:       `{sl:,.2f}` \\({self._esc(sl_pips)}\\)",
            f"TP:       `{tp:,.2f}` \\({self._esc(tp_pips)}\\)",
            f"Lots:     `{lot_size}`",
            f"R:R:      `{self._esc(rr)}`",
            self._esc(DIVIDER),
        ]
        self._enqueue("\n".join(lines))

    async def notify_trade_close(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        reason: str,
    ) -> None:
        """
        Send a trade-close alert.

        reason: "tp" | "sl" | "manual" (or any string)
        """
        reason_lower = reason.lower()
        if "tp" in reason_lower:
            reason_emoji = "✅"
            reason_label = "TP Hit"
        elif "sl" in reason_lower:
            reason_emoji = "❌"
            reason_label = "SL Hit"
        else:
            reason_emoji = "⏹"
            reason_label = reason.title()

        pnl_emoji = _pnl_emoji(pnl)
        pnl_sign = "+" if pnl >= 0 else ""
        side_emoji = _side_emoji(side)

        lines = [
            f"{reason_emoji} *TRADE CLOSED — {self._esc(symbol.upper())}*",
            self._esc(DIVIDER),
            f"Side:   {side_emoji} {self._esc(side.upper())}",
            f"Entry:  `{entry_price:,.2f}`",
            f"Exit:   `{exit_price:,.2f}`",
            f"PnL:    {pnl_emoji} `{pnl_sign}{pnl:,.2f} USD`",
            f"Reason: {reason_emoji} {self._esc(reason_label)}",
            self._esc(DIVIDER),
        ]
        self._enqueue("\n".join(lines))

    async def notify_daily_summary(
        self,
        total_trades: int,
        win_rate: float,
        pnl: float,
        equity: float,
        drawdown: float,
    ) -> None:
        """Send the end-of-day performance summary."""
        pnl_emoji = _pnl_emoji(pnl)
        pnl_sign = "+" if pnl >= 0 else ""
        dd_indicator = "🟢" if drawdown < 5 else "🟡" if drawdown < 10 else "🔴"

        lines = [
            "📊 *DAILY SUMMARY*",
            self._esc(DIVIDER),
            f"Date:        `{datetime.now(timezone.utc).strftime('%Y-%m-%d')}`",
            f"Trades:      `{total_trades}`",
            f"Win Rate:    `{win_rate:.1f}%`",
            f"PnL:         {pnl_emoji} `{pnl_sign}{pnl:,.2f} USD`",
            f"Equity:      `{equity:,.2f} USD`",
            f"Drawdown:    {dd_indicator} `{drawdown:.2f}%`",
            self._esc(DIVIDER),
        ]
        self._enqueue("\n".join(lines))

    async def notify_risk_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "high",
    ) -> None:
        """
        Send a risk alert.

        severity: "low" | "medium" | "high" | "critical"
        """
        sev_emoji = _severity_emoji(severity)
        lines = [
            f"🚨 *RISK ALERT — {self._esc(alert_type.upper())}*",
            self._esc(DIVIDER),
            f"Severity: {sev_emoji} {self._esc(severity.upper())}",
            f"Message:  {self._esc(message)}",
            f"Time:     `{_now_str()}`",
            self._esc(DIVIDER),
        ]
        self._enqueue("\n".join(lines))

    async def notify_strategy_signal(
        self,
        strategy_name: str,
        signal: str,
        confidence: float,
    ) -> None:
        """
        Send a strategy signal notification.

        signal: "BUY" | "SELL" | "HOLD" | any label
        confidence: 0.0 – 1.0  (will be shown as %)
        """
        sig_up = signal.upper()
        if sig_up == "BUY":
            sig_emoji = "🟢"
        elif sig_up == "SELL":
            sig_emoji = "🔴"
        else:
            sig_emoji = "🔵"

        conf_pct = confidence * 100 if confidence <= 1.0 else confidence
        conf_bar = self._confidence_bar(conf_pct)

        lines = [
            f"📡 *STRATEGY SIGNAL*",
            self._esc(DIVIDER),
            f"Strategy:   {self._esc(strategy_name)}",
            f"Signal:     {sig_emoji} *{self._esc(sig_up)}*",
            f"Confidence: `{conf_pct:.1f}%` {conf_bar}",
            f"Time:       `{_now_str()}`",
            self._esc(DIVIDER),
        ]
        self._enqueue("\n".join(lines))

    # ─────────────────── convenience helpers ─────────────────────────────────

    @staticmethod
    def _confidence_bar(pct: float, width: int = 10) -> str:
        """Return a simple text bar like ▓▓▓▓▓░░░░░ for confidence."""
        filled = round(pct / 100 * width)
        return "▓" * filled + "░" * (width - filled)

    async def send_raw(self, text: str, parse_mode: str = "MarkdownV2") -> None:
        """Enqueue a raw message string (advanced use)."""
        self._enqueue(text, parse_mode=parse_mode)
