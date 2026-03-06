"""
Risk Management - Daily loss limit, max drawdown, etc.
"""

from datetime import datetime


class RiskManager:
    """Handles all risk limits"""
    
    def __init__(self, config):
        self.config = config
        self.daily_pnl = 0
        self.last_day = ""
        self.peak_equity = 0
        self.initial_equity = 0
    
    def check(self, equity: float) -> tuple:
        """Returns (can_trade: bool, reason: str)"""
        current_day = datetime.now().strftime("%Y-%m-%d")
        
        # Reset daily stats
        if current_day != self.last_day:
            self.last_day = current_day
            self.daily_pnl = 0
        
        # Track peak
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        if self.initial_equity == 0:
            self.initial_equity = equity
        
        # Check daily loss
        if self.daily_pnl <= -self.config.max_daily_loss:
            return False, f"Daily loss limit: {self.daily_pnl:.2f}"
        
        # Check drawdown
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - equity) / self.peak_equity * 100
            if drawdown >= self.config.max_drawdown:
                return False, f"Max drawdown: {drawdown:.1f}%"
        
        return True, ""
    
    def update_pnl(self, pnl: float):
        self.daily_pnl += pnl
