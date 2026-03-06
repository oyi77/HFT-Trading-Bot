"""
WebSocket Client for Real-time Market Data
Simulates MT5's OnTick functionality with real-time price streaming
"""

import json
import time
import threading
from typing import Callable, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tick:
    """Represents a single price tick"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: int
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def midpoint(self) -> float:
        return (self.bid + self.ask) / 2


class TickSimulator:
    """
    Simulates real-time ticks from candle data
    Generates realistic tick-by-tick movement within candle range
    """
    
    def __init__(self, candles: list):
        self.candles = candles
        self.current_idx = 0
        self.tick_count = 0
        
    def next_tick(self) -> Optional[Tick]:
        """Generate next simulated tick"""
        if self.current_idx >= len(self.candles):
            return None
        
        candle = self.candles[self.current_idx]
        
        # Generate multiple ticks per candle
        ticks_per_candle = 10
        tick_in_candle = self.tick_count % ticks_per_candle
        
        # Interpolate price within candle range
        progress = tick_in_candle / ticks_per_candle
        price = candle['low'] + (candle['high'] - candle['low']) * progress
        
        # Add some noise for bid/ask
        spread = 0.02  # 2 cents for XAU
        bid = price - spread / 2
        ask = price + spread / 2
        
        tick = Tick(
            symbol="XAUUSD",
            bid=round(bid, 2),
            ask=round(ask, 2),
            last=round(price, 2),
            volume=int(candle.get('volume', 0) / ticks_per_candle),
            timestamp=candle['timestamp'] + (tick_in_candle * 6000)  # Add milliseconds
        )
        
        self.tick_count += 1
        if self.tick_count % ticks_per_candle == 0:
            self.current_idx += 1
            
        return tick


class WebSocketManager:
    """
    Manages WebSocket connections for real-time data
    Falls back to polling if WebSocket not available
    """
    
    def __init__(self):
        self.subscribers: Dict[str, list] = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.tick_simulators: Dict[str, TickSimulator] = {}
        
    def subscribe(self, symbol: str, callback: Callable[[Tick], None]):
        """Subscribe to tick updates for a symbol"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)
        print(f"📡 Subscribed to {symbol}")
        
    def unsubscribe(self, symbol: str, callback: Callable[[Tick], None]):
        """Unsubscribe from tick updates"""
        if symbol in self.subscribers:
            self.subscribers[symbol].remove(callback)
            
    def start_simulation(self, symbol: str, candles: list):
        """Start simulating ticks from candle data"""
        self.tick_simulators[symbol] = TickSimulator(candles)
        
    def start(self, tick_interval: float = 0.1):
        """Start the WebSocket/polling loop"""
        self.running = True
        self.thread = threading.Thread(target=self._run, args=(tick_interval,))
        self.thread.daemon = True
        self.thread.start()
        print("🚀 WebSocket manager started")
        
    def stop(self):
        """Stop the WebSocket/polling loop"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("🛑 WebSocket manager stopped")
        
    def _run(self, tick_interval: float):
        """Main loop for generating ticks"""
        while self.running:
            for symbol, simulator in self.tick_simulators.items():
                tick = simulator.next_tick()
                if tick:
                    self._notify(symbol, tick)
                    
            time.sleep(tick_interval)
            
    def _notify(self, symbol: str, tick: Tick):
        """Notify all subscribers"""
        if symbol in self.subscribers:
            for callback in self.subscribers[symbol]:
                try:
                    callback(tick)
                except Exception as e:
                    print(f"Error notifying subscriber: {e}")


class ExnessWebSocket:
    """
    Real-time data feed from Exness
    Uses WebSocket if available, otherwise polling
    """
    
    def __init__(self, provider):
        self.provider = provider
        self.ws_manager = WebSocketManager()
        self.price_cache: Dict[str, Tick] = {}
        
    def connect(self):
        """Connect to WebSocket"""
        # For now, use polling mode
        # In production, implement actual WebSocket connection
        print("🔗 Connecting to real-time feed...")
        return True
        
    def subscribe_ticks(self, symbol: str, callback: Callable[[Tick], None]):
        """Subscribe to tick updates"""
        self.ws_manager.subscribe(symbol, callback)
        
    def get_last_tick(self, symbol: str) -> Optional[Tick]:
        """Get last known tick"""
        return self.price_cache.get(symbol)
        
    def start_polling(self, symbols: list, interval: float = 1.0):
        """Start polling for price updates"""
        def poll():
            while True:
                for symbol in symbols:
                    try:
                        price = self.provider.get_price(symbol)
                        if price > 0:
                            tick = Tick(
                                symbol=symbol,
                                bid=price - 0.01,
                                ask=price + 0.01,
                                last=price,
                                volume=0,
                                timestamp=int(time.time() * 1000)
                            )
                            self.price_cache[symbol] = tick
                            self.ws_manager._notify(symbol, tick)
                    except Exception as e:
                        print(f"Polling error: {e}")
                time.sleep(interval)
                
        thread = threading.Thread(target=poll)
        thread.daemon = True
        thread.start()
