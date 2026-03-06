"""State persistence for crash recovery."""

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
import threading
import hashlib


@dataclass
class TradingState:
    """Serializable trading state."""

    timestamp: str
    symbol: str
    balance: float
    equity: float
    positions: List[Dict[str, Any]]
    trades_count: int
    daily_pnl: float
    config_hash: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingState":
        return cls(**data)


class StateManager:
    """Manages trading state persistence for crash recovery."""

    def __init__(
        self,
        state_dir: str = "data",
        auto_save_interval: float = 30.0,
        max_backups: int = 5,
    ):
        self.state_dir = state_dir
        self.auto_save_interval = auto_save_interval
        self.max_backups = max_backups
        self._lock = threading.Lock()
        self._last_save_time = 0.0
        self._state_file = os.path.join(state_dir, "state.json")
        self._backup_dir = os.path.join(state_dir, "backups")

        # Ensure directories exist
        os.makedirs(state_dir, exist_ok=True)
        os.makedirs(self._backup_dir, exist_ok=True)

    def save(
        self,
        symbol: str,
        balance: float,
        equity: float,
        positions: List[Dict[str, Any]],
        trades_count: int,
        daily_pnl: float,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Save current trading state.

        Args:
            symbol: Trading symbol
            balance: Account balance
            equity: Account equity
            positions: List of open positions
            trades_count: Number of trades
            daily_pnl: Daily P&L
            config: Optional config for hash
            metadata: Optional additional data

        Returns:
            True if save successful
        """
        try:
            config_hash = self._hash_config(config or {})

            state = TradingState(
                timestamp=datetime.utcnow().isoformat(),
                symbol=symbol,
                balance=balance,
                equity=equity,
                positions=positions,
                trades_count=trades_count,
                daily_pnl=daily_pnl,
                config_hash=config_hash,
                metadata=metadata or {},
            )

            with self._lock:
                # Write to temp file first
                temp_file = self._state_file + ".tmp"
                with open(temp_file, "w") as f:
                    json.dump(state.to_dict(), f, indent=2)

                # Atomic rename
                os.replace(temp_file, self._state_file)

                self._last_save_time = time.time()

            return True

        except Exception as e:
            print(f"State save error: {e}")
            return False

    def load(self) -> Optional[TradingState]:
        """Load saved trading state.

        Returns:
            TradingState if exists and valid, None otherwise
        """
        try:
            if not os.path.exists(self._state_file):
                return None

            with self._lock:
                with open(self._state_file, "r") as f:
                    data = json.load(f)

            return TradingState.from_dict(data)

        except Exception as e:
            print(f"State load error: {e}")
            return None

    def backup(self) -> bool:
        """Create a backup of current state.

        Returns:
            True if backup successful
        """
        try:
            if not os.path.exists(self._state_file):
                return False

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self._backup_dir, f"state_{timestamp}.json")

            with self._lock:
                # Copy current state to backup
                with open(self._state_file, "r") as src:
                    with open(backup_file, "w") as dst:
                        dst.write(src.read())

                # Cleanup old backups
                self._cleanup_backups()

            return True

        except Exception as e:
            print(f"Backup error: {e}")
            return False

    def restore(self, backup_name: Optional[str] = None) -> Optional[TradingState]:
        """Restore from a backup.

        Args:
            backup_name: Specific backup file, or None for latest

        Returns:
            TradingState if restore successful
        """
        try:
            if backup_name:
                backup_file = os.path.join(self._backup_dir, backup_name)
            else:
                # Find latest backup
                backups = sorted(os.listdir(self._backup_dir), reverse=True)
                if not backups:
                    return None
                backup_file = os.path.join(self._backup_dir, backups[0])

            if not os.path.exists(backup_file):
                return None

            with self._lock:
                with open(backup_file, "r") as f:
                    data = json.load(f)

            return TradingState.from_dict(data)

        except Exception as e:
            print(f"Restore error: {e}")
            return None

    def should_auto_save(self) -> bool:
        """Check if auto-save interval has passed."""
        return time.time() - self._last_save_time >= self.auto_save_interval

    def clear(self) -> bool:
        """Clear saved state."""
        try:
            with self._lock:
                if os.path.exists(self._state_file):
                    os.remove(self._state_file)
            return True
        except Exception as e:
            print(f"Clear error: {e}")
            return False

    def _cleanup_backups(self) -> None:
        """Remove old backups beyond max_backups."""
        backups = sorted(os.listdir(self._backup_dir), reverse=True)
        for old_backup in backups[self.max_backups :]:
            os.remove(os.path.join(self._backup_dir, old_backup))

    def _hash_config(self, config: Dict[str, Any]) -> str:
        """Create a hash of config for validation."""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]

    def validate_state(self, state: TradingState, config: Dict[str, Any]) -> bool:
        """Validate state matches current config.

        Args:
            state: Loaded state
            config: Current config

        Returns:
            True if state is valid for current config
        """
        current_hash = self._hash_config(config)
        return state.config_hash == current_hash
