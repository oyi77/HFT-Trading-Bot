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
- BBMacdRsiStrategy: Bollinger Band + MACD + RSI mean reversion & breakout
- AIStrategy: ML-powered GradientBoosting strategy with self-training
- ZeroLagStrategy: ZeroLag EMA + ATR bands with martingale grid & runner TP
"""

from trading_bot.strategy.xau_hedging import XAUHedgingStrategy, XAUHedgingConfig
from trading_bot.strategy.grid import GridStrategy, GridConfig
from trading_bot.strategy.trend import TrendStrategy, TrendConfig
from trading_bot.strategy.hft import HFTStrategy, HFTConfig
from trading_bot.strategy.nfi import NFIStrategy, NFIConfig
from trading_bot.strategy.ib_breakout import IBBreakoutStrategy, IBBreakoutConfig
from trading_bot.strategy.momentum import MomentumGridStrategy, MomentumGridConfig
from trading_bot.strategy.seven_candle import SevenCandleStrategy, SevenCandleConfig
from trading_bot.strategy.bb_macd_rsi import BBMacdRsiStrategy, BBMacdRsiConfig
from trading_bot.strategy.ai_strategy import AIStrategy, AIStrategyConfig
from trading_bot.strategy.zerolag import ZeroLagStrategy, ZeroLagConfig

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
    "BBMacdRsiStrategy",
    "BBMacdRsiConfig",
    "AIStrategy",
    "AIStrategyConfig",
    "ZeroLagStrategy",
    "ZeroLagConfig",
]

