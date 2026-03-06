"""
Strategy Runner - Automation Engine like MT5's EA
Handles strategy execution, position management, and monitoring
"""

import time
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from trading_bot.core.interfaces import Exchange
from trading_bot.strategy.base import Strategy
from trading_bot.exchange.websocket_client import WebSocketManager, Tick


@dataclass
class RunnerConfig:
    """Configuration for strategy runner"""
    symbol: str
    timeframe: str = "1m"
    enable_trading: bool = True
    max_positions: int = 2
    check_interval: float = 1.0  # seconds
    session_filter: bool = True
    
    # Risk management
    max_daily_loss: Optional[float] = None  # Max daily loss in $
    max_drawdown_pct: Optional[float] = None  # Max drawdown %
    
    # Notifications
    on_trade_open: Optional[Callable] = None
    on_trade_close: Optional[Callable] = None
    on_error: Optional[Callable] = None


class StrategyRunner:
    """
    Automated Strategy Runner - Like MT5 Expert Advisor
    
    Features:
    - Real-time tick processing
    - Automatic position management
    - Session filtering
    - Risk management
    - Trade notifications
    - Performance tracking
    """
    
    def __init__(
        self,
        strategy: Strategy,
        exchange: Exchange,
        config: RunnerConfig
    ):
        self.strategy = strategy
        self.exchange = exchange
        self.config = config
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.ws_manager = WebSocketManager()
        
        # Stats
        self.start_time: Optional[datetime] = None
        self.ticks_processed = 0
        self.trades_executed = 0
        self.errors_count = 0
        self.daily_pnl = 0.0
        self.peak_equity = 0.0
        
        # Pending orders (for hedge strategy)
        self.pending_orders: Dict[str, Any] = {}
        
    def start(self):
        """Start the strategy runner"""
        if self.running:
            print("⚠️ Runner already started")
            return
            
        self.running = True
        self.start_time = datetime.now()
        
        # Get initial equity for drawdown calc
        self.peak_equity = self.exchange.get_equity()
        
        # Start WebSocket or polling
        self.ws_manager.start()
        
        # Subscribe to ticks
        self.ws_manager.subscribe(self.config.symbol, self._on_tick)
        
        # Start main loop
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"🚀 Strategy runner started for {self.config.symbol}")
        print(f"   Trading enabled: {self.config.enable_trading}")
        
    def stop(self):
        """Stop the strategy runner"""
        self.running = False
        self.ws_manager.stop()
        
        if self.thread:
            self.thread.join(timeout=5)
            
        print("🛑 Strategy runner stopped")
        self.print_stats()
        
    def _run_loop(self):
        """Main execution loop"""
        while self.running:
            try:
                # Check risk limits
                if self._check_risk_limits():
                    print("⚠️ Risk limit reached, pausing trading")
                    time.sleep(60)
                    continue
                
                # Check session if enabled
                if self.config.session_filter and not self._is_trading_session():
                    time.sleep(self.config.check_interval)
                    continue
                
                # Poll for price updates (backup if no WebSocket)
                self._poll_price()
                
                time.sleep(self.config.check_interval)
                
            except Exception as e:
                self.errors_count += 1
                print(f"❌ Error in main loop: {e}")
                if self.config.on_error:
                    self.config.on_error(e)
                    
    def _on_tick(self, tick: Tick):
        """Process incoming tick"""
        if not self.running:
            return
            
        try:
            self.ticks_processed += 1
            
            # Get current positions
            positions = self.exchange.get_positions(self.config.symbol)
            
            # Call strategy
            signal = self.strategy.on_tick(
                price=tick.last,
                bid=tick.bid,
                ask=tick.ask,
                positions=positions,
                timestamp=tick.timestamp
            )
            
            if signal and self.config.enable_trading:
                self._execute_signal(signal, tick)
                
        except Exception as e:
            self.errors_count += 1
            print(f"❌ Error processing tick: {e}")
            
    def _execute_signal(self, signal: Dict, tick: Tick):
        """Execute trading signal"""
        action = signal.get('action')
        
        if action == 'open':
            self._open_position(signal, tick)
        elif action == 'close':
            self._close_position(signal)
        elif action == 'modify':
            self._modify_position(signal)
        elif action == 'pending':
            self._place_pending_order(signal, tick)
            
    def _open_position(self, signal: Dict, tick: Tick):
        """Open new position"""
        # Check max positions
        positions = self.exchange.get_positions(self.config.symbol)
        if len(positions) >= self.config.max_positions:
            return
            
        side = signal.get('side', 'long')
        volume = signal.get('amount', 0.01)
        sl = signal.get('sl')
        tp = signal.get('tp')
        
        # Determine entry price
        entry_price = tick.ask if side == 'long' else tick.bid
        
        ticket = self.exchange.open_position(
            symbol=self.config.symbol,
            side=side,
            volume=volume,
            sl=sl,
            tp=tp,
            price=entry_price
        )
        
        if ticket:
            self.trades_executed += 1
            print(f"✅ Opened {side} position [Ticket: {ticket}]")
            
            if self.config.on_trade_open:
                self.config.on_trade_open({
                    'ticket': ticket,
                    'side': side,
                    'volume': volume,
                    'price': entry_price,
                    'sl': sl,
                    'tp': tp
                })
                
    def _close_position(self, signal: Dict):
        """Close position"""
        position_id = signal.get('position_id')
        if position_id:
            success = self.exchange.close_position(position_id, self.config.symbol)
            if success:
                print(f"✅ Closed position #{position_id}")
                if self.config.on_trade_close:
                    self.config.on_trade_close({'position_id': position_id})
                    
    def _modify_position(self, signal: Dict):
        """Modify position SL/TP"""
        position_id = signal.get('position_id')
        sl = signal.get('sl')
        tp = signal.get('tp')
        
        if position_id:
            self.exchange.modify_position_sl(position_id, sl, tp)
            
    def _place_pending_order(self, signal: Dict, tick: Tick):
        """Place pending order (for hedging)"""
        # Store pending order for later execution
        order_id = f"pending_{time.time()}"
        self.pending_orders[order_id] = {
            'signal': signal,
            'placed_at': tick.timestamp
        }
        print(f"📋 Pending order placed: {order_id}")
        
    def _check_risk_limits(self) -> bool:
        """Check if risk limits are breached"""
        current_equity = self.exchange.get_equity()
        
        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            
        # Check drawdown
        if self.config.max_drawdown_pct:
            drawdown = (self.peak_equity - current_equity) / self.peak_equity * 100
            if drawdown >= self.config.max_drawdown_pct:
                print(f"⚠️ Max drawdown reached: {drawdown:.2f}%")
                return True
                
        # Check daily loss
        if self.config.max_daily_loss:
            if self.daily_pnl <= -self.config.max_daily_loss:
                print(f"⚠️ Max daily loss reached: ${self.daily_pnl:.2f}")
                return True
                
        return False
        
    def _is_trading_session(self) -> bool:
        """Check if currently in allowed trading session"""
        now = datetime.utcnow()
        hour = now.hour
        
        # London: 7-17, NY: 17-22
        # Skip Asia (0-7) and overnight (22-24)
        return 7 <= hour < 22
        
    def _poll_price(self):
        """Poll for price updates (backup method)"""
        # This is handled by WebSocket, but can be used as backup
        pass
        
    def print_stats(self):
        """Print performance statistics"""
        runtime = datetime.now() - self.start_time if self.start_time else None
        
        print("\n" + "=" * 50)
        print("📊 STRATEGY RUNNER STATS")
        print("=" * 50)
        print(f"Runtime:          {runtime}")
        print(f"Ticks processed:  {self.ticks_processed}")
        print(f"Trades executed:  {self.trades_executed}")
        print(f"Errors:           {self.errors_count}")
        print(f"Current equity:   ${self.exchange.get_equity():.2f}")
        print("=" * 50)


class MultiSymbolRunner:
    """Run multiple strategies on different symbols simultaneously"""
    
    def __init__(self):
        self.runners: Dict[str, StrategyRunner] = {}
        
    def add_runner(self, name: str, runner: StrategyRunner):
        """Add a strategy runner"""
        self.runners[name] = runner
        
    def start_all(self):
        """Start all runners"""
        for name, runner in self.runners.items():
            print(f"Starting {name}...")
            runner.start()
            
    def stop_all(self):
        """Stop all runners"""
        for name, runner in self.runners.items():
            print(f"Stopping {name}...")
            runner.stop()
            
    def get_status(self) -> Dict:
        """Get status of all runners"""
        return {
            name: {
                'running': runner.running,
                'ticks': runner.ticks_processed,
                'trades': runner.trades_executed
            }
            for name, runner in self.runners.items()
        }
