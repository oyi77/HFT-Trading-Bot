"""
Data models for the trading system
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


class TradeMode(Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class OHLCV:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    amount: float
    price: float = 0
    stop_price: float = 0
    sl: float = 0
    tp: float = 0
    status: str = "open"
    timestamp: int = 0


@dataclass
class Position:
    id: str
    symbol: str
    side: PositionSide
    entry_price: float
    amount: float
    current_price: float = 0
    unrealized_pnl: float = 0
    sl: float = 0
    tp: float = 0
    open_time: int = 0


@dataclass
class Trade:
    id: str
    symbol: str
    side: OrderSide
    price: float
    amount: float
    pnl: float = 0
    fee: float = 0
    timestamp: int = 0


@dataclass
class Balance:
    total: float = 0
    free: float = 0
    used: float = 0
    unrealized_pnl: float = 0
    
    @property
    def equity(self) -> float:
        return self.total + self.unrealized_pnl


@dataclass
class Config:
    mode: TradeMode = TradeMode.BACKTEST
    symbol: str = "BTC/USDT"
    exchange: str = "binance"
    api_key: str = ""
    api_secret: str = ""
    
    lots: float = 0.01
    use_auto_lot: bool = False
    risk_percent: float = 1.0
    
    stop_loss: int = 1500
    take_profit: int = 0
    trailing: int = 500
    trail_start: int = 1000
    x_distance: int = 300
    start_direction: int = 0
    
    max_daily_loss: float = 100
    max_drawdown: float = 20
    
    use_break_even: bool = True
    break_even_profit: int = 500
    break_even_offset: int = 10
    
    initial_balance: float = 10000
    fee_rate: float = 0.001
    
    use_session_filter: bool = False
    use_asia_session: bool = True
    use_london_open: bool = True
    use_london_peak: bool = True
    use_ny_session: bool = True
