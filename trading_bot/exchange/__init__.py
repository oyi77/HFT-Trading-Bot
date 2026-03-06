"""
Exchange providers for Trading Bot
"""
from trading_bot.exchange.exness_web import ExnessWebProvider, create_exness_web_provider
from trading_bot.exchange.paper_trading import PaperTradingProvider
from trading_bot.exchange.simulator import SimulatorExchange

# CCXT import is optional (may fail on some Python versions)
try:
    from trading_bot.exchange.ccxt import CCXTExchange
except ImportError:
    CCXTExchange = None

__all__ = [
    'ExnessWebProvider',
    'create_exness_web_provider',
    'CCXTExchange',
    'PaperTradingProvider',
    'SimulatorExchange',
]
