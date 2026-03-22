"""
Risk Management — unified risk gateway.
Combines daily loss limit, max drawdown, circuit breaker, and loss streak.
"""

import logging
from datetime import datetime
from typing import Tuple

from trading_bot.risk.circuit_breaker import TradingCircuitBreaker as CircuitBreaker
from trading_bot.risk.loss_streak import LossStreakManager, LossStreakConfig

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Unified risk gateway for the trading engine.

    Checks (in order):
    1. Circuit breaker state (OPEN = halt)
    2. Daily loss limit
    3. Max drawdown from peak equity
    4. Loss streak cooldown

    Usage
    -----
        rm = RiskManager(config)
        can_trade, reason = rm.check(equity)
        if can_trade:
            lot = rm.get_lot_size(base_lot)
            # … open position …
        rm.on_trade_result(pnl)   # call after every close
    """

    def __init__(self, config):
        self.config = config

        # Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            max_consecutive_losses=getattr(config, "max_consecutive_losses", 5),
            max_daily_loss_pct=getattr(config, "max_daily_loss_pct", 6.0),
            max_drawdown_pct=getattr(config, "max_drawdown", 20.0),
            rapid_loss_window_minutes=getattr(config, "rapid_loss_window_minutes", 30),
            rapid_loss_count=getattr(config, "rapid_loss_count", 3),
            cooldown_minutes=getattr(config, "circuit_cooldown_minutes", 60),
        )

        # Loss Streak Manager
        streak_cfg = LossStreakConfig(
            thresholds={3: 0.75, 5: 0.50, 7: 0.25},
            max_losses_before_pause=getattr(config, "max_consecutive_losses", 8),
            cooldown_seconds=3600,
            wins_to_reset=2,
        )
        self.loss_streak = LossStreakManager(streak_cfg)

        # Daily stats
        self.daily_pnl: float = 0.0
        self.last_day: str = ""
        self.peak_equity: float = 0.0
        self.initial_equity: float = 0.0

    def check(self, equity: float) -> Tuple[bool, str]:
        """
        Returns (can_trade: bool, reason: str).
        Call before every trade decision.
        """
        current_day = datetime.now().strftime("%Y-%m-%d")

        # Reset daily stats on new day
        if current_day != self.last_day:
            self.last_day = current_day
            self.daily_pnl = 0.0

        # Track peak
        if equity > self.peak_equity:
            self.peak_equity = equity

        if self.initial_equity == 0:
            self.initial_equity = equity

        # 1. Circuit breaker
        cb_ok, cb_reason = self.circuit_breaker.check(equity)
        if not cb_ok:
            return False, f"[CircuitBreaker] {cb_reason}"

        # 2. Daily loss
        max_daily = getattr(self.config, "max_daily_loss", 0)
        if max_daily > 0 and self.daily_pnl <= -max_daily:
            return False, f"[DailyLoss] limit reached: {self.daily_pnl:.2f}"

        # 3. Max drawdown
        max_dd = getattr(self.config, "max_drawdown", 0)
        if max_dd > 0 and self.peak_equity > 0:
            drawdown_pct = (self.peak_equity - equity) / self.peak_equity * 100
            if drawdown_pct >= max_dd:
                return False, f"[Drawdown] {drawdown_pct:.1f}% >= {max_dd}%"

        # 4. Loss streak cooldown
        pause, streak_reason = self.loss_streak.should_pause()
        if pause:
            return False, f"[LossStreak] {streak_reason}"

        return True, ""

    def on_trade_result(self, pnl: float):
        """Call after every closed trade with its P&L"""
        self.daily_pnl += pnl
        self.loss_streak.on_trade_result(pnl)
        self.circuit_breaker.on_trade_result(pnl)
        logger.debug(f"RiskManager: trade PnL={pnl:+.2f} | daily={self.daily_pnl:+.2f}")

    def get_lot_size(self, base_lot: float) -> float:
        """Return streak-adjusted lot size"""
        return self.loss_streak.get_adjusted_lot_size(base_lot)

    def get_stats(self) -> dict:
        return {
            "daily_pnl": self.daily_pnl,
            "peak_equity": self.peak_equity,
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "loss_streak": self.loss_streak.get_stats(),
        }
