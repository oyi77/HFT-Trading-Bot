"""
Trading Strategies Package

Available strategies:
- XAUHedgingStrategy: Gold hedging with session awareness
- GridStrategy: Range-based grid trading
- TrendStrategy: EMA crossover trend following
- HFTStrategy: High frequency scalping
"""

from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.grid import GridStrategy
from trading_bot.strategy.trend import TrendStrategy
from trading_bot.strategy.hft import HFTStrategy, HFTConfig

__all__ = [
    "XAUHedgingStrategy",
    "XAUHedgingConfig",
    "GridStrategy",
    "TrendStrategy",
    "HFTStrategy",
    "HFTConfig",
]
