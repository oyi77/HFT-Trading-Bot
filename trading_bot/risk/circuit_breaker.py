"""Circuit Breaker pattern for API failure protection."""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Optional


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Circuit breaker statistics."""

    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0
    last_state_change: float = field(default_factory=time.time)
    total_requests: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Failure threshold exceeded, all requests blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        self._check_recovery()
        return self._state

    @property
    def stats(self) -> CircuitStats:
        return self._stats

    def can_execute(self) -> bool:
        self._check_recovery()
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            return False
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        self._stats.successes += 1
        self._stats.total_requests += 1
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)
            self._stats.failures = 0
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            self._stats.failures = 0

    def record_failure(self) -> None:
        self._stats.failures += 1
        self._stats.total_failures += 1
        self._stats.total_requests += 1
        self._stats.last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            if self._stats.failures >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def force_open(self) -> None:
        self._transition_to(CircuitState.OPEN)

    def force_close(self) -> None:
        self._transition_to(CircuitState.CLOSED)
        self._stats.failures = 0
        self._half_open_calls = 0

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0

    def _check_recovery(self) -> None:
        if self._state == CircuitState.OPEN:
            time_since_failure = time.time() - self._stats.last_failure_time
            if time_since_failure >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_calls = 0

    def _transition_to(self, new_state: CircuitState) -> None:
        if self._state != new_state:
            self._state = new_state
            self._stats.last_state_change = time.time()

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
            f"failures={self._stats.failures}/{self.failure_threshold})"
        )


class CircuitBreakerError(Exception):
    """Raised when circuit is open and request is blocked."""

    def __init__(self, breaker: CircuitBreaker):
        self.breaker = breaker
        super().__init__(
            f"Circuit '{breaker.name}' is {breaker.state.value} "
            f"(failures: {breaker.stats.failures}/{breaker.failure_threshold})"
        )


# =============================================================================
# TradingCircuitBreaker — trading risk monitoring pattern from master
# =============================================================================


class TradingCircuitBreaker:
    """Monitors trading health metrics and halts trading when risk thresholds
    are breached.

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
        import logging
        from datetime import datetime, timezone

        self.logger = logging.getLogger(__name__)
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.rapid_loss_window_minutes = rapid_loss_window_minutes
        self.rapid_loss_count = rapid_loss_count
        self.cooldown_minutes = cooldown_minutes
        self._state = CircuitState.CLOSED
        self._tripped_at: Optional[datetime] = None
        self._trip_reason: str = ""
        self._consecutive_losses: int = 0
        self._daily_loss_pct: float = 0.0
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._recent_loss_times: list = []
        self._last_reset_day: str = ""
        self._start_of_day_equity: float = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    def check(self, equity: Optional[float] = None) -> tuple:
        if equity is not None:
            self._update_equity(equity)
        if self._state == CircuitState.OPEN:
            self._try_recover()
        if self._state == CircuitState.CLOSED:
            return True, ""
        elif self._state == CircuitState.HALF_OPEN:
            return True, "HALF_OPEN: test trade allowed"
        else:
            elapsed = self._seconds_since_trip()
            remaining = max(0, self.cooldown_minutes * 60 - elapsed)
            return (
                False,
                f"Circuit OPEN — {self._trip_reason} "
                f"(cooldown: {int(remaining // 60)}m {int(remaining % 60)}s remaining)",
            )

    def on_trade_result(self, pnl: float):
        if pnl < 0:
            self.record_loss(abs(pnl))
        else:
            self.record_win()

    def record_loss(self, loss_amount: float = 0.0):
        from datetime import datetime, timezone

        self._consecutive_losses += 1
        now = datetime.now(timezone.utc)
        self._recent_loss_times.append(now)
        cutoff = now.timestamp() - self.rapid_loss_window_minutes * 60
        self._recent_loss_times = [
            t for t in self._recent_loss_times if t.timestamp() >= cutoff
        ]
        self._evaluate_triggers()

    def record_win(self):
        self._consecutive_losses = 0
        if self._state == CircuitState.HALF_OPEN:
            self._close()

    def record_equity(self, equity: float):
        self._update_equity(equity)
        self._evaluate_triggers()

    def get_stats(self) -> dict:
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

    def reset(self):
        self._close()
        self.logger.info("TradingCircuitBreaker manually reset to CLOSED")

    def _update_equity(self, equity: float):
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_day:
            self._last_reset_day = today
            self._start_of_day_equity = (
                equity if equity > 0 else self._start_of_day_equity
            )
            self._daily_loss_pct = 0.0
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._start_of_day_equity > 0:
            self._daily_loss_pct = (
                (self._start_of_day_equity - equity) / self._start_of_day_equity * 100
            )

    def _evaluate_triggers(self):
        if self._state != CircuitState.CLOSED:
            return
        if self._consecutive_losses >= self.max_consecutive_losses:
            self._open(
                f"consecutive losses ({self._consecutive_losses}/{self.max_consecutive_losses})"
            )
            return
        if self._daily_loss_pct >= self.max_daily_loss_pct:
            self._open(
                f"daily loss {self._daily_loss_pct:.1f}% >= {self.max_daily_loss_pct}%"
            )
            return
        if self._peak_equity > 0 and self._current_equity > 0:
            drawdown = (
                (self._peak_equity - self._current_equity) / self._peak_equity * 100
            )
            if drawdown >= self.max_drawdown_pct:
                self._open(f"drawdown {drawdown:.1f}% >= {self.max_drawdown_pct}%")
                return
        if len(self._recent_loss_times) >= self.rapid_loss_count:
            self._open(
                f"rapid losses: {len(self._recent_loss_times)} losses "
                f"in {self.rapid_loss_window_minutes} minutes"
            )

    def _open(self, reason: str):
        self._state = CircuitState.OPEN
        from datetime import datetime, timezone

        self._tripped_at = datetime.now(timezone.utc)
        self._trip_reason = reason
        self.logger.warning(f"TradingCircuitBreaker OPENED — {reason}")

    def _close(self):
        self._state = CircuitState.CLOSED
        self._tripped_at = None
        self._trip_reason = ""
        self._consecutive_losses = 0
        self._recent_loss_times.clear()
        self.logger.info("TradingCircuitBreaker CLOSED (normal operation)")

    def _try_recover(self):
        if self._tripped_at is None:
            return
        if self._seconds_since_trip() >= self.cooldown_minutes * 60:
            self._state = CircuitState.HALF_OPEN
            self.logger.info(
                "TradingCircuitBreaker → HALF_OPEN (cooldown elapsed, testing recovery)"
            )

    def _seconds_since_trip(self) -> float:
        if self._tripped_at is None:
            return 0.0
        from datetime import datetime, timezone

        return (datetime.now(timezone.utc) - self._tripped_at).total_seconds()
