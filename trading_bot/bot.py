"""
Main Trading Bot - Orchestrates all components
"""

import logging
import time
from typing import Optional

from trading_bot.core.models import Config, TradeMode, OrderSide
from trading_bot.exchange.base import Exchange
from trading_bot.exchange.ccxt import CCXTExchange
from trading_bot.exchange.simulator import Simulator
from trading_bot.strategy.base import Strategy
from trading_bot.risk.manager import RiskManager

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot"""
    
    def __init__(self, config: Config):
        self.config = config
        self.exchange: Optional[Exchange] = None
        self.strategy: Optional[Strategy] = None
        self.risk = RiskManager(config)
        
    def setup(self, strategy_class: type):
        """Initialize components"""
        # Create exchange
        if self.config.mode == TradeMode.BACKTEST:
            self.exchange = Simulator(self.config)
        else:
            self.exchange = CCXTExchange(self.config)
            if not self.exchange.connect():
                raise ConnectionError("Failed to connect")
        
        # Create strategy
        self.strategy = strategy_class(self.config)
        
        logger.info(f"Bot ready: {self.config.mode.value} | {strategy_class.__name__}")
    
    def run(self):
        """Main loop"""
        if not self.exchange or not self.strategy:
            raise RuntimeError("Not setup")
        
        logger.info("=" * 50)
        logger.info("STARTING BOT")
        logger.info("=" * 50)
        
        if self.config.mode == TradeMode.BACKTEST:
            self._run_backtest()
        else:
            self._run_live()
    
    def _run_backtest(self):
        """Backtest loop"""
        if isinstance(self.exchange, Simulator):
            # Generate data if none loaded
            if not self.exchange.data:
                # Use XAU data for XAU strategy, else crypto
                if 'XAU' in self.config.symbol.upper():
                    self.exchange.generate_xau_data(90)
                else:
                    self.exchange.generate_synthetic_data(90)
        
        while self.exchange.tick():
            self._process_tick()
        
        self._print_results()
    
    def _run_live(self):
        """Live trading loop"""
        while True:
            try:
                self._process_tick()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(5)
    
    def _process_tick(self):
        """Single tick processing"""
        bid, ask = self.exchange.get_price()
        price = (bid + ask) / 2
        
        balance = self.exchange.get_balance()
        positions = self.exchange.positions
        
        # Check risk
        can_trade, reason = self.risk.check(balance.equity)
        if not can_trade:
            logger.warning(f"Risk limit: {reason}")
            return
        
        # Get signal (pass timestamp for session-aware strategies)
        timestamp = None
        if isinstance(self.exchange, Simulator):
            timestamp = self.exchange._current_time
        action = self.strategy.on_tick(price, bid, ask, positions, timestamp)
        
        if action:
            self._execute(action)
    
    def _execute(self, action: dict):
        """Execute action from strategy"""
        action_type = action.get('action')
        
        if action_type == 'open':
            self.exchange.create_order(
                action['side'],
                action['amount'],
                action.get('price', 0),
                action.get('sl', 0),
                action.get('tp', 0)
            )
        elif action_type == 'close':
            for pos in self.exchange.positions:
                if pos.id == action['position_id']:
                    trade = self.exchange.close_position(pos)
                    if trade:
                        self.risk.update_pnl(trade.pnl)
    
    def _print_results(self):
        """Print backtest results"""
        if not isinstance(self.exchange, Simulator):
            return
        
        trades = self.exchange.trades
        if not trades:
            logger.info("No trades executed")
            return
        
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in trades)
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        
        final = self.exchange.get_balance()
        
        print("\n" + "=" * 50)
        print("BACKTEST RESULTS")
        print("=" * 50)
        print(f"Initial: ${self.config.initial_balance:,.2f}")
        print(f"Final:   ${final.equity:,.2f}")
        print(f"Return:  {((final.equity/self.config.initial_balance)-1)*100:+.2f}%")
        print(f"Trades:  {len(trades)}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Wins: {len(wins)}, Losses: {len(losses)}")
        if wins:
            print(f"Avg Win: ${sum(t.pnl for t in wins)/len(wins):.2f}")
        if losses:
            print(f"Avg Loss: ${sum(t.pnl for t in losses)/len(losses):.2f}")
        print("=" * 50)
