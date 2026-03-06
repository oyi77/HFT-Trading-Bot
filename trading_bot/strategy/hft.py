"""
HFT (High Frequency Trading) Strategy
Combines scalping, order book analysis, and micro-momentum detection
Optimized for very short-term trades with tight risk management
"""

from typing import Dict, Optional, List, Deque, Any
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide


@dataclass
class HFTConfig:
    """Configuration for HFT Strategy"""

    # Trade parameters
    lots: float = 0.01  # Lot size per trade
    max_positions: int = 5  # Max concurrent positions

    # Scalping parameters
    min_spread_pips: int = 2  # Minimum spread to trade (pips)
    profit_target_pips: int = 3  # Take profit in pips (scalping)
    stop_loss_pips: int = 5  # Stop loss in pips (tight)

    # Momentum parameters
    momentum_lookback: int = 10  # Ticks for momentum calculation
    momentum_threshold: float = 0.0002  # 0.02% price change threshold

    # Order book parameters
    spread_threshold: float = 0.0001  # 0.01% spread threshold
    imbalance_threshold: float = 1.5  # Bid/ask volume ratio threshold

    # Order book depth analysis
    use_orderbook_depth: bool = True
    depth_levels: int = 5  # Number of depth levels to analyze
    depth_imbalance_threshold: float = 2.0  # Depth imbalance ratio threshold

    # Volume profile analysis
    use_volume_profile: bool = True
    volume_lookback: int = 20  # Bars for volume profile
    volume_threshold: float = 1.3  # Volume spike threshold (vs avg)
    poc_proximity_pips: int = 10  # Proximity to POC (Point of Control)

    # Time-based exit
    max_hold_seconds: int = 30  # Maximum position hold time

    # Risk management
    max_daily_loss: float = 50.0  # Max daily loss in account currency
    cooldown_after_loss: int = 60  # Seconds to cooldown after loss

    # Volatility filter
    min_volatility: float = 0.0001  # Minimum volatility to trade
    max_volatility: float = 0.001  # Maximum volatility (avoid chaotic markets)


class HFTStrategy(Strategy):
    """
    High Frequency Trading Strategy

    Key characteristics:
    - Microsecond/millisecond level decisions
    - Small profit targets (3-5 pips)
    - Tight stops (5 pips)
    - Quick position turnover (avg 10-30 seconds)
    - Order book imbalance detection
    - Momentum scalping
    - Volatility filtering

    Combines elements from:
    - Grid: Quick profit taking at levels
    - Trend: Micro-momentum detection
    - Hedging: Tight risk management
    """

    def __init__(self, config: HFTConfig = None):
        if config is None:
            config = HFTConfig()
        super().__init__(config)

        # Price history for analysis
        self.price_history: Deque[Dict] = deque(maxlen=100)
        self.tick_count = 0

        # Trade tracking
        self.daily_pnl = 0.0
        self.last_trade_time = 0
        self.cooldown_until = 0
        self.trades_today = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # Session tracking
        self.session_start = datetime.now()

        # Point value (0.01 for XAU/USD, 0.0001 for forex)
        self.point_value = 0.01

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        """
        HFT decision logic - runs on every tick
        """
        self.tick_count += 1
        current_time = timestamp or int(datetime.now().timestamp())

        # Check cooldown
        if current_time < self.cooldown_until:
            return None

        # Check daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss:
            return None

        # Store price data
        spread = ask - bid
        mid_price = (bid + ask) / 2

        price_data = {
            "timestamp": current_time,
            "price": price,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "mid": mid_price,
        }
        self.price_history.append(price_data)

        # Manage existing positions first
        action = self._manage_positions(positions, bid, ask, current_time)
        if action:
            return action

        # Check if we can open new positions
        if len(positions) >= self.config.max_positions:
            return None

        # Run entry analysis every tick
        return self._analyze_entry(bid, ask, spread, mid_price)

    def _manage_positions(
        self, positions: List[Position], bid: float, ask: float, current_time: int
    ) -> Optional[Dict]:
        """Manage existing positions - quick exits"""
        for pos in positions:
            # Time-based exit
            hold_time = current_time - pos.open_time
            if hold_time > self.config.max_hold_seconds:
                return {"action": "close", "position_id": pos.id}

            # Profit target exit (scalping)
            point = self.point_value
            if pos.side == PositionSide.LONG:
                profit_pips = (bid - pos.entry_price) / point
                loss_pips = (pos.entry_price - ask) / point
            else:
                profit_pips = (pos.entry_price - ask) / point
                loss_pips = (bid - pos.entry_price) / point

            # Take profit
            if profit_pips >= self.config.profit_target_pips:
                self._record_trade(profit_pips)
                return {"action": "close", "position_id": pos.id}

            # Stop loss
            if loss_pips >= self.config.stop_loss_pips:
                self._record_trade(-loss_pips)
                self.cooldown_until = current_time + self.config.cooldown_after_loss
                return {"action": "close", "position_id": pos.id}

        return None

    def _analyze_entry(
        self, bid: float, ask: float, spread: float, mid_price: float
    ) -> Optional[Dict]:
        """Analyze market conditions for entry with order book depth and volume profile"""
        point = self.point_value
        spread_pips = spread / point

        # Filter: Spread too wide
        if spread_pips < self.config.min_spread_pips:
            return None

        # Calculate momentum
        momentum = self._calculate_momentum()
        if momentum is None:
            return None

        # Calculate volatility
        volatility = self._calculate_volatility()
        if volatility is None:
            return None

        # Filter: Volatility check
        if not (self.config.min_volatility <= volatility <= self.config.max_volatility):
            return None

        # Order book depth analysis
        depth_signal = 0
        if self.config.use_orderbook_depth:
            depth_analysis = self._analyze_orderbook_depth(bid, ask)
            depth_signal = depth_analysis.get("signal", 0)

        # Volume profile analysis
        volume_signal = 0
        poc_proximity = True
        if self.config.use_volume_profile:
            vp_analysis = self._analyze_volume_profile()
            volume_signal = vp_analysis.get("volume_signal", 0)
            poc = vp_analysis.get("poc", mid_price)
            poc_proximity = self._check_poc_proximity(mid_price, poc)

        # Combined entry logic
        # Require momentum + at least one confirmation (depth or volume)
        entry_score = 0
        if momentum > self.config.momentum_threshold:
            entry_score = 1
        elif momentum < -self.config.momentum_threshold:
            entry_score = -1

        # Apply confirmations
        if entry_score > 0:
            # Bullish momentum
            if depth_signal > 0:
                entry_score += 1
            if volume_signal > 0 and poc_proximity:
                entry_score += 1

            # Require at least one confirmation
            if entry_score >= 2:
                sl = bid - self.config.stop_loss_pips * point
                tp = ask + self.config.profit_target_pips * point
                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        elif entry_score < 0:
            # Bearish momentum
            if depth_signal < 0:
                entry_score -= 1
            if volume_signal > 0 and poc_proximity:
                entry_score -= 1

            # Require at least one confirmation
            if entry_score <= -2:
                sl = ask + self.config.stop_loss_pips * point
                tp = bid - self.config.profit_target_pips * point
                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": self.config.lots,
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                }

        return None

    def _calculate_momentum(self) -> Optional[float]:
        """Calculate short-term price momentum"""
        if len(self.price_history) < self.config.momentum_lookback:
            return None

        # Get recent prices
        recent = list(self.price_history)[-self.config.momentum_lookback :]

        # Calculate price change
        first_price = recent[0]["mid"]
        last_price = recent[-1]["mid"]

        if first_price == 0:
            return None

        momentum = (last_price - first_price) / first_price
        return momentum

    def _calculate_volatility(self) -> Optional[float]:
        """Calculate recent volatility (standard deviation of returns)"""
        if len(self.price_history) < 20:
            return None

        prices = [p["mid"] for p in self.price_history]

        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] != 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

        if len(returns) < 10:
            return None

        # Calculate standard deviation
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        volatility = variance**0.5

        return volatility

    def _analyze_orderbook_depth(self, bid: float, ask: float) -> Dict[str, Any]:
        """
        Analyze order book depth using price history
        Simulates depth by analyzing price action and volume
        """
        if len(self.price_history) < self.config.depth_levels + 5:
            return {"bullish_depth": 1.0, "bearish_depth": 1.0, "signal": 0}

        recent = list(self.price_history)[-self.config.depth_levels :]

        # Calculate bid/ask pressure from recent candles
        bullish_pressure = 0
        bearish_pressure = 0

        for candle in recent:
            open_p = candle.get("open", candle["mid"])
            close_p = candle["mid"]
            volume = candle.get("volume", 100)

            if close_p > open_p:
                bullish_pressure += volume
            elif close_p < open_p:
                bearish_pressure += volume

        # Calculate depth ratios
        total_pressure = bullish_pressure + bearish_pressure
        if total_pressure == 0:
            return {"bullish_depth": 1.0, "bearish_depth": 1.0, "signal": 0}

        bullish_depth = bullish_pressure / total_pressure
        bearish_depth = bearish_pressure / total_pressure

        # Generate signal based on depth imbalance
        depth_ratio = bullish_depth / bearish_depth if bearish_depth > 0 else 999

        signal = 0
        if depth_ratio > self.config.depth_imbalance_threshold:
            signal = 1  # Bullish
        elif depth_ratio < (1 / self.config.depth_imbalance_threshold):
            signal = -1  # Bearish

        return {
            "bullish_depth": bullish_depth,
            "bearish_depth": bearish_depth,
            "depth_ratio": depth_ratio,
            "signal": signal,
        }

    def _analyze_volume_profile(self) -> Dict[str, Any]:
        """
        Analyze volume profile to identify key levels
        Uses volume at price (VAP) concept
        """
        if len(self.price_history) < self.config.volume_lookback:
            return {
                "poc": 0,
                "value_area_high": 0,
                "value_area_low": 0,
                "volume_signal": 0,
            }

        recent = list(self.price_history)[-self.config.volume_lookback :]

        # Calculate average volume
        volumes = [c.get("volume", 100) for c in recent]
        avg_volume = sum(volumes) / len(volumes) if volumes else 100

        # Current volume
        current_volume = recent[-1].get("volume", 100)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Calculate POC (Point of Control) - price with highest volume
        price_volume = {}
        for candle in recent:
            price = round(candle["mid"], 2)
            vol = candle.get("volume", 100)
            price_volume[price] = price_volume.get(price, 0) + vol

        poc = (
            max(price_volume.keys(), key=lambda x: price_volume[x])
            if price_volume
            else recent[-1]["mid"]
        )

        # Calculate Value Area (70% of volume)
        sorted_prices = sorted(price_volume.items(), key=lambda x: x[1], reverse=True)
        total_vol = sum(price_volume.values())
        cumulative_vol = 0
        value_area_prices = []

        for price, vol in sorted_prices:
            cumulative_vol += vol
            value_area_prices.append(price)
            if cumulative_vol >= total_vol * 0.7:
                break

        value_area_high = max(value_area_prices) if value_area_prices else poc
        value_area_low = min(value_area_prices) if value_area_prices else poc

        # Volume signal
        volume_signal = 0
        if volume_ratio > self.config.volume_threshold:
            volume_signal = 1  # Volume spike detected

        return {
            "poc": poc,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
            "avg_volume": avg_volume,
            "current_volume": current_volume,
            "volume_ratio": volume_ratio,
            "volume_signal": volume_signal,
        }

    def _check_poc_proximity(self, price: float, poc: float) -> bool:
        """Check if price is near Point of Control"""
        point = self.point_value
        distance = abs(price - poc) / point
        return distance <= self.config.poc_proximity_pips

    def _record_trade(self, profit_pips: float):
        """Record trade result for statistics"""
        self.trades_today += 1
        if profit_pips > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Update daily PnL (approximate)
        pip_value = self.config.lots * 10  # Approximate $10 per pip per lot
        self.daily_pnl += profit_pips * pip_value

    def get_stats(self) -> Dict:
        """Get HFT strategy statistics"""
        total_trades = self.winning_trades + self.losing_trades
        win_rate = (self.winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "trades_today": self.trades_today,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(win_rate, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "tick_count": self.tick_count,
            "in_cooldown": datetime.now().timestamp() < self.cooldown_until,
        }
