"""
Trading Strategies Package

Available strategies:
- XAUHedgingStrategy: Gold hedging with session awareness
- GridStrategy: Range-based grid trading
- TrendStrategy: EMA crossover trend following
- HFTStrategy: High frequency scalping
- NFIStrategy: NostalgiaForInfinity multi-mode trend following
- IBBreakoutStrategy: Initial Balance breakout (+411% documented)
- ScalpingStrategy: Simple momentum-based scalping
- SevenCandleStrategy: 7 Candle Breakout strategy
"""

from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.grid import GridStrategy, GridConfig
from trading_bot.strategy.trend import TrendStrategy, TrendConfig
from trading_bot.strategy.hft import HFTStrategy, HFTConfig
from trading_bot.strategy.nfi import NFIStrategy, NFIConfig
from trading_bot.strategy.ib_breakout import IBBreakoutStrategy, IBBreakoutConfig
from trading_bot.strategy.momentum import MomentumGridStrategy, MomentumGridConfig
from trading_bot.strategy.seven_candle import SevenCandleStrategy, SevenCandleConfig

__all__ = [
    "XAUHedgingStrategy",
    "XAUHedgingConfig",
    "GridStrategy",
    "GridConfig",
    "TrendStrategy",
    "TrendConfig",
    "HFTStrategy",
    "HFTConfig",
    "NFIStrategy",
    "NFIConfig",
    "IBBreakoutStrategy",
    "IBBreakoutConfig",
    "MomentumGridStrategy",
    "MomentumGridConfig",
    "SevenCandleStrategy",
    "SevenCandleConfig",
]
