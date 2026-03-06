#!/usr/bin/env python3
"""
Trading Bot Entry Point

Usage:
    python main.py --mode backtest --strategy hedging --symbol BTC/USDT
    python main.py --mode paper --exchange bybit --api-key XXX --api-secret YYY
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.core.models import Config, TradeMode
from trading_bot.bot import TradingBot
from trading_bot.strategy.hedging import HedgingStrategy
from trading_bot.strategy.trend import TrendStrategy
from trading_bot.strategy.xau_hedging import XAUHedgingStrategy


def main():
    parser = argparse.ArgumentParser(description='Trading Bot')
    parser.add_argument('--mode', choices=['backtest', 'paper', 'live'], default='backtest')
    parser.add_argument('--strategy', choices=['hedging', 'trend', 'xau'], default='hedging')
    parser.add_argument('--symbol', default='BTC/USDT')
    parser.add_argument('--exchange', default='binance')
    parser.add_argument('--api-key', default='')
    parser.add_argument('--api-secret', default='')
    parser.add_argument('--lots', type=float, default=0.01)
    parser.add_argument('--stop-loss', type=int, default=1500)
    parser.add_argument('--balance', type=float, default=10000)
    
    args = parser.parse_args()
    
    # Create config
    config = Config(
        mode=TradeMode(args.mode),
        symbol=args.symbol,
        exchange=args.exchange,
        api_key=args.api_key,
        api_secret=args.api_secret,
        lots=args.lots,
        stop_loss=args.stop_loss,
        initial_balance=args.balance
    )
    
    # Get strategy
    strategies = {
        'hedging': HedgingStrategy,
        'trend': TrendStrategy,
        'xau': XAUHedgingStrategy
    }
    
    # Run
    bot = TradingBot(config)
    bot.setup(strategies[args.strategy])
    bot.run()


if __name__ == '__main__':
    main()
