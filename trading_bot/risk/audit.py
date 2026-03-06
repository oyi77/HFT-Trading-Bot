"""Audit logging for trading signals and orders."""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import threading


class AuditEventType(Enum):
    """Types of audit events."""

    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_VALIDATED = "signal_validated"
    SIGNAL_REJECTED = "signal_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_FAILED = "order_failed"
    RISK_CHECK_PASSED = "risk_check_passed"
    RISK_CHECK_FAILED = "risk_check_failed"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_CLOSE = "circuit_breaker_close"


@dataclass
class AuditEvent:
    """Audit event record."""

    timestamp: str
    event_type: str
    symbol: str
    details: Dict[str, Any]
    result: str  # "success" or "failure"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditLogger:
    """Thread-safe audit logger for trading events."""

    def __init__(self, log_dir: str = "logs", enabled: bool = True):
        self.log_dir = log_dir
        self.enabled = enabled
        self._lock = threading.Lock()
        self._buffer: List[AuditEvent] = []
        self._buffer_size = 100

        if enabled and not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def log(
        self,
        event_type: AuditEventType,
        symbol: str,
        details: Dict[str, Any],
        result: str = "success",
        reason: str = "",
    ) -> None:
        """Log an audit event."""
        if not self.enabled:
            return

        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type.value,
            symbol=symbol,
            details=details,
            result=result,
            reason=reason,
        )

        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self._buffer_size:
                self._flush()

    def log_signal(
        self,
        symbol: str,
        signal: Optional[Dict[str, Any]],
        result: str = "success",
        reason: str = "",
    ) -> None:
        """Log a trading signal event."""
        self.log(
            AuditEventType.SIGNAL_GENERATED,
            symbol,
            {"signal": signal or {}},
            result,
            reason,
        )

    def log_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        result: str = "success",
        reason: str = "",
    ) -> None:
        """Log an order event."""
        self.log(
            AuditEventType.ORDER_SUBMITTED,
            symbol,
            {"side": side, "amount": amount, "price": price},
            result,
            reason,
        )

    def log_risk_check(
        self,
        symbol: str,
        check_type: str,
        passed: bool,
        reason: str = "",
    ) -> None:
        """Log a risk check event."""
        event_type = (
            AuditEventType.RISK_CHECK_PASSED
            if passed
            else AuditEventType.RISK_CHECK_FAILED
        )
        self.log(
            event_type,
            symbol,
            {"check_type": check_type},
            "success" if passed else "failure",
            reason,
        )

    def log_circuit_breaker(
        self,
        symbol: str,
        state: str,
        failures: int,
    ) -> None:
        """Log a circuit breaker state change."""
        event_type = (
            AuditEventType.CIRCUIT_BREAKER_OPEN
            if state == "open"
            else AuditEventType.CIRCUIT_BREAKER_CLOSE
        )
        self.log(
            event_type,
            symbol,
            {"state": state, "failures": failures},
            "success",
        )

    def _flush(self) -> None:
        """Write buffer to file."""
        if not self._buffer:
            return

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"audit_{date_str}.jsonl")

        with open(log_file, "a") as f:
            for event in self._buffer:
                f.write(event.to_json() + "\n")

        self._buffer.clear()

    def flush(self) -> None:
        """Public method to flush buffer."""
        with self._lock:
            self._flush()

    def get_recent_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get recent events from buffer."""
        with self._lock:
            return [e.to_dict() for e in self._buffer[-count:]]

    def close(self) -> None:
        """Flush and close the logger."""
        self.flush()
