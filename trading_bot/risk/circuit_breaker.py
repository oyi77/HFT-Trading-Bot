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

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        >>>
        >>> async def safe_api_call():
        ...     if not breaker.can_execute():
        ...         raise Exception("Circuit is OPEN")
        ...     try:
        ...         result = await api_call()
        ...         breaker.record_success()
        ...         return result
        ...     except Exception as e:
        ...         breaker.record_failure()
        ...         raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        name: str = "default",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Max calls allowed in HALF_OPEN state
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        self._check_recovery()
        return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats

    def can_execute(self) -> bool:
        """Check if a request can be executed.

        Returns:
            True if request should proceed, False if blocked
        """
        self._check_recovery()

        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            return False

        # HALF_OPEN: allow limited requests
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True

        return False

    def record_success(self) -> None:
        """Record a successful request."""
        self._stats.successes += 1
        self._stats.total_requests += 1

        if self._state == CircuitState.HALF_OPEN:
            # Recovery successful, close circuit
            self._transition_to(CircuitState.CLOSED)
            self._stats.failures = 0
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._stats.failures = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self._stats.failures += 1
        self._stats.total_failures += 1
        self._stats.total_requests += 1
        self._stats.last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Recovery failed, open circuit again
            self._transition_to(CircuitState.OPEN)
            self._half_open_calls = 0
        elif self._state == CircuitState.CLOSED:
            if self._stats.failures >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def force_open(self) -> None:
        """Manually open the circuit."""
        self._transition_to(CircuitState.OPEN)

    def force_close(self) -> None:
        """Manually close the circuit."""
        self._transition_to(CircuitState.CLOSED)
        self._stats.failures = 0
        self._half_open_calls = 0

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0

    def _check_recovery(self) -> None:
        """Check if enough time has passed to attempt recovery."""
        if self._state == CircuitState.OPEN:
            time_since_failure = time.time() - self._stats.last_failure_time
            if time_since_failure >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_calls = 0

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
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
