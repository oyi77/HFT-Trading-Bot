"""
Circuit Breaker — monitors trading health and halts trading when risk thresholds
are breached.

States
------
CLOSED   — Normal operation; trading is allowed.
OPEN     — Trading halted; triggered by a risk breach.
HALF_OPEN — Cooldown period has elapsed; one test trade is allowed to verify
            recovery before returning to CLOSED.

Ported from telegram-ai-trade/src/core/error_handler.py (CircuitBreaker) and
telegram-ai-trade/src/services/config_manager.py (consecutive_loss_rules).
Rewritten as a standalone, HFT-Trading-Bot-style class.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Tuple

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Monitors trading health metrics and opens/closes the trading circuit
    based on configurable risk thresholds.

    Parameters
    ----------
    max_consecutive_losses : int
        Number of consecutive losses that trips the breaker (default 4).
    max_daily_loss_pct : float
        Maximum daily loss as a percentage of starting equity (default 6.0 %).
    max_drawdown_pct : float
        Maximum peak-to-trough drawdown percentage (default 10.0 %).
    rapid_loss_window_minutes : int
        Rolling window (minutes) used to detect a rapid-loss burst (default 30).
    rapid_loss_count : int
        Number of losses inside ``rapid_loss_window_minutes`` that trips the
        breaker (default 3).
    cooldown_minutes : int
        Minutes the breaker stays OPEN before entering HALF_OPEN (default 60).
    """

    def __init__(
        self,
        max_consecutive_losses: int = 4,
        max_daily_loss_pct: float = 6.0,
        max_drawdown_pct: float = 10.0,
        rapid_loss_window_minutes: int = 30,
        rapid_loss_count: int = 3,
        cooldown_minutes: int = 60,
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.rapid_loss_window_minutes = rapid_loss_window_minutes
        self.rapid_loss_count = rapid_loss_count
        self.cooldown_minutes = cooldown_minutes

        # Internal state
        self._state: CircuitState = CircuitState.CLOSED
        self._tripped_at: datetime | None = None
        self._trip_reason: str = ""

        # Metrics (updated externally via record_*)
        self._consecutive_losses: int = 0
        self._daily_loss_pct: float = 0.0
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._recent_loss_times: list[datetime] = []

        # Daily reset tracking
        self._last_reset_day: str = ""
        self._start_of_day_equity: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        return self._state

    def check(self, equity: float | None = None) -> Tuple[bool, str]:
        """
        Primary integration point.

        Returns
        -------
        (can_trade, reason)
            can_trade — True when trading is allowed.
            reason    — Empty string when allowed; human-readable explanation
                        when blocked.
        """
        if equity is not None:
            self._update_equity(equity)

        # Attempt auto-recovery
        if self._state == CircuitState.OPEN:
            self._try_recover()

        if self._state == CircuitState.CLOSED:
            return True, ""
        elif self._state == CircuitState.HALF_OPEN:
            return True, "HALF_OPEN: test trade allowed"
        else:  # OPEN
            elapsed = self._seconds_since_trip()
            remaining = max(0, self.cooldown_minutes * 60 - elapsed)
            return (
                False,
                f"Circuit OPEN — {self._trip_reason} "
                f"(cooldown: {int(remaining // 60)}m {int(remaining % 60)}s remaining)",
            )

    def record_loss(self, loss_amount: float = 0.0):
        """Call after every losing trade."""
        self._consecutive_losses += 1
        now = datetime.now(timezone.utc)
        self._recent_loss_times.append(now)

        # Prune stale entries outside the rapid-loss window
        cutoff = now.timestamp() - self.rapid_loss_window_minutes * 60
        self._recent_loss_times = [
            t for t in self._recent_loss_times if t.timestamp() >= cutoff
        ]

        # Evaluate triggers
        self._evaluate_triggers()

    def record_win(self):
        """Call after every winning trade. Resets consecutive-loss counter."""
        self._consecutive_losses = 0
        # A win in HALF_OPEN → full recovery
        if self._state == CircuitState.HALF_OPEN:
            self._close()

    def record_equity(self, equity: float):
        """Update equity snapshot. Called independently from record_loss/win."""
        self._update_equity(equity)
        self._evaluate_triggers()

    def reset(self):
        """Manually force circuit back to CLOSED (e.g. after human review)."""
        self._close()
        logger.info("CircuitBreaker manually reset to CLOSED")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_equity(self, equity: float):
        """Maintain peak equity and daily loss percentage."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_day:
            self._last_reset_day = today
            self._start_of_day_equity = equity if equity > 0 else self._start_of_day_equity
            self._daily_loss_pct = 0.0

        self._current_equity = equity

        if equity > self._peak_equity:
            self._peak_equity = equity

        if self._start_of_day_equity > 0:
            self._daily_loss_pct = (
                (self._start_of_day_equity - equity) / self._start_of_day_equity * 100
            )

    def _evaluate_triggers(self):
        """Check all trip conditions and open the circuit if any are breached."""
        if self._state != CircuitState.CLOSED:
            return  # Already tripped — don't double-trip

        # 1. Consecutive loss limit
        if self._consecutive_losses >= self.max_consecutive_losses:
            self._open(
                f"consecutive losses ({self._consecutive_losses}/{self.max_consecutive_losses})"
            )
            return

        # 2. Daily loss %
        if self._daily_loss_pct >= self.max_daily_loss_pct:
            self._open(
                f"daily loss {self._daily_loss_pct:.1f}% >= {self.max_daily_loss_pct}%"
            )
            return

        # 3. Max drawdown
        if self._peak_equity > 0 and self._current_equity > 0:
            drawdown = (
                (self._peak_equity - self._current_equity) / self._peak_equity * 100
            )
            if drawdown >= self.max_drawdown_pct:
                self._open(
                    f"drawdown {drawdown:.1f}% >= {self.max_drawdown_pct}%"
                )
                return

        # 4. Rapid loss rate
        if len(self._recent_loss_times) >= self.rapid_loss_count:
            self._open(
                f"rapid losses: {len(self._recent_loss_times)} losses "
                f"in {self.rapid_loss_window_minutes} minutes"
            )

    def _open(self, reason: str):
        self._state = CircuitState.OPEN
        self._tripped_at = datetime.now(timezone.utc)
        self._trip_reason = reason
        logger.warning(f"CircuitBreaker OPENED — {reason}")

    def _close(self):
        self._state = CircuitState.CLOSED
        self._tripped_at = None
        self._trip_reason = ""
        self._consecutive_losses = 0
        self._recent_loss_times.clear()
        logger.info("CircuitBreaker CLOSED (normal operation)")

    def _try_recover(self):
        """Transition OPEN → HALF_OPEN once the cooldown has elapsed."""
        if self._tripped_at is None:
            return
        if self._seconds_since_trip() >= self.cooldown_minutes * 60:
            self._state = CircuitState.HALF_OPEN
            logger.info(
                "CircuitBreaker → HALF_OPEN (cooldown elapsed, testing recovery)"
            )

    def _seconds_since_trip(self) -> float:
        if self._tripped_at is None:
            return 0.0
        return (datetime.now(timezone.utc) - self._tripped_at).total_seconds()

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Return a snapshot of the breaker's current state for logging/UI."""
        return {
            "state": self._state.value,
            "trip_reason": self._trip_reason,
            "consecutive_losses": self._consecutive_losses,
            "daily_loss_pct": round(self._daily_loss_pct, 2),
            "peak_equity": round(self._peak_equity, 2),
            "current_equity": round(self._current_equity, 2),
            "recent_rapid_losses": len(self._recent_loss_times),
            "cooldown_minutes": self.cooldown_minutes,
        }
