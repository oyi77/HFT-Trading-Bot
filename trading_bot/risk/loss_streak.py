"""
Loss Streak Manager — progressive lot reduction + cooldown on consecutive losses.
Ported from telegram-ai-trade's consecutive loss management system.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LossStreakConfig:
    """Configuration for loss streak management"""

    # Consecutive loss thresholds → lot multipliers
    # e.g. after 3 losses, use 75% of base lot
    thresholds: dict = field(default_factory=lambda: {
        3: 0.75,   # 3 losses → 75% lot
        5: 0.50,   # 5 losses → 50% lot
        7: 0.25,   # 7 losses → 25% lot
    })

    # Pause trading after this many consecutive losses
    max_losses_before_pause: int = 8

    # Cooldown duration in seconds after hitting max_losses_before_pause
    cooldown_seconds: int = 3600  # 1 hour

    # Reset multiplier after this many consecutive wins
    wins_to_reset: int = 2

    # Minimum lot multiplier (floor)
    min_multiplier: float = 0.25


class LossStreakManager:
    """
    Manages lot sizing and trading pauses based on consecutive loss streaks.

    Strategy:
    - Track consecutive losses and wins
    - Progressively reduce lot size after hitting thresholds
    - Force cooldown pause after hitting max_losses_before_pause
    - Reset to normal after wins_to_reset consecutive wins
    """

    def __init__(self, config: LossStreakConfig = None):
        self.config = config or LossStreakConfig()

        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.total_losses: int = 0
        self.total_wins: int = 0

        self._pause_until: float = 0.0  # Unix timestamp

    # ─── Public API ───────────────────────────────────────────────────────────

    def on_trade_result(self, pnl: float):
        """Call after every closed trade with its P&L"""
        if pnl > 0:
            self._on_win()
        else:
            self._on_loss()

    def get_adjusted_lot_size(self, base_lot: float) -> float:
        """
        Return adjusted lot size based on current streak.
        Returns base_lot unchanged if streak is below all thresholds.
        """
        multiplier = self._get_multiplier()
        adjusted = round(base_lot * multiplier, 2)
        return max(adjusted, 0.01)  # Never go below broker minimum

    def should_pause(self) -> tuple:
        """
        Returns (should_pause: bool, reason: str)
        """
        if self._pause_until > time.time():
            remaining = int(self._pause_until - time.time())
            mins = remaining // 60
            return True, f"Loss streak cooldown: {mins}m remaining ({self.consecutive_losses} losses)"

        if self.consecutive_losses >= self.config.max_losses_before_pause:
            self._start_cooldown()
            return True, f"Max consecutive losses ({self.consecutive_losses}) — cooling down {self.config.cooldown_seconds // 60}m"

        return False, ""

    def reset(self):
        """Hard reset — call when starting a new trading session"""
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self._pause_until = 0.0
        logger.info("LossStreakManager reset")

    def get_stats(self) -> dict:
        return {
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "total_losses": self.total_losses,
            "total_wins": self.total_wins,
            "current_multiplier": self._get_multiplier(),
            "in_cooldown": self._pause_until > time.time(),
            "cooldown_remaining_s": max(0, int(self._pause_until - time.time())),
        }

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _on_win(self):
        self.consecutive_wins += 1
        self.consecutive_losses = 0
        self.total_wins += 1

        if self.consecutive_wins >= self.config.wins_to_reset:
            if self._pause_until > 0:
                logger.info(f"LossStreak: {self.consecutive_wins} wins — resetting pause/multiplier")
            self._pause_until = 0.0  # Clear cooldown on recovery

        logger.debug(f"LossStreak: WIN #{self.consecutive_wins} | multiplier={self._get_multiplier():.2f}")

    def _on_loss(self):
        self.consecutive_losses += 1
        self.consecutive_wins = 0
        self.total_losses += 1
        logger.info(f"LossStreak: LOSS #{self.consecutive_losses} | multiplier={self._get_multiplier():.2f}")

    def _get_multiplier(self) -> float:
        """Get current lot multiplier based on loss count"""
        multiplier = 1.0
        for threshold in sorted(self.config.thresholds.keys()):
            if self.consecutive_losses >= threshold:
                multiplier = self.config.thresholds[threshold]
        return max(multiplier, self.config.min_multiplier)

    def _start_cooldown(self):
        if self._pause_until <= time.time():  # Don't restart if already cooling
            self._pause_until = time.time() + self.config.cooldown_seconds
            logger.warning(
                f"LossStreak: Cooldown started — {self.consecutive_losses} consecutive losses. "
                f"Resume at {time.strftime('%H:%M', time.localtime(self._pause_until))}"
            )
