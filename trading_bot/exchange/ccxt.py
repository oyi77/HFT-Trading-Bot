"""
CCXT Exchange implementation - supports 100+ exchanges
"""

import logging
from typing import List, Optional

import ccxt

from trading_bot.exchange.base import Exchange
from trading_bot.core.models import (
    Order, OrderSide, Position, Trade, Balance, OHLCV, Config
)

logger = logging.getLogger(__name__)


class CCXTExchange(Exchange):
    """Real exchange via CCXT"""
    
    def __init__(self, config: Config):
        self.config = config
        self.exchange = None
        
    def connect(self) -> bool:
        try:
            exchange_class = getattr(ccxt, self.config.exchange)
            self.exchange = exchange_class({
                'apiKey': self.config.api_key,
                'secret': self.config.api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            self.exchange.load_markets()
            logger.info(f"Connected to {self.config.exchange}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def get_balance(self) -> Balance:
        try:
            bal = self.exchange.fetch_balance()
            quote = self.config.symbol.split('/')[1]
            return Balance(
                total=bal['total'].get(quote, 0),
                free=bal['free'].get(quote, 0),
                used=bal['used'].get(quote, 0)
            )
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return Balance()
    
    def get_price(self) -> tuple:
        try:
            ticker = self.exchange.fetch_ticker(self.config.symbol)
            return ticker.get('bid', ticker['last']), ticker.get('ask', ticker['last'])
        except Exception as e:
            logger.error(f"Price error: {e}")
            return 0, 0
    
    def create_order(self, side: OrderSide, amount: float,
                     price: float = 0, sl: float = 0, tp: float = 0) -> Optional[Order]:
        try:
            order_type = 'limit' if price > 0 else 'market'
            result = self.exchange.create_order(
                self.config.symbol, order_type, side.value, amount, price
            )
            return Order(
                id=result['id'],
                symbol=self.config.symbol,
                side=side,
                amount=amount,
                price=result.get('price', price),
                sl=sl,
                tp=tp,
                status=result['status'],
                timestamp=result['timestamp']
            )
        except Exception as e:
            logger.error(f"Order error: {e}")
            return None
    
    def close_position(self, position: Position) -> Optional[Trade]:
        side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        return self.create_order(side, position.amount)
    
    def fetch_ohlcv(self, timeframe: str = "1h", limit: int = 100) -> List[OHLCV]:
        try:
            data = self.exchange.fetch_ohlcv(self.config.symbol, timeframe, limit=limit)
            return [OHLCV(c[0], c[1], c[2], c[3], c[4], c[5]) for c in data]
        except Exception as e:
            logger.error(f"OHLCV error: {e}")
            return []
    
    @property
    def positions(self) -> List[Position]:
        # For spot, positions are holdings
        # For futures, would fetch from exchange
        return []
