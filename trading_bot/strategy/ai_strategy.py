"""
AI-Integrated Trading Strategy
Uses Gradient Boosting ML model to predict price direction from technical indicators.

Features:
- Self-training: learns from market data, retrains periodically
- 15+ technical indicator features (EMA, RSI, MACD, BB, ATR, momentum)
- Confidence gating: only trades when prediction confidence > threshold
- Fallback: rule-based logic when model isn't ready
- Zero external APIs: 100% local inference using scikit-learn
"""

import warnings
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

import numpy as np

from trading_bot.strategy.base import Strategy
from trading_bot.core.models import Position, PositionSide, OrderSide
from trading_bot.utils.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_sma,
)

# Suppress sklearn convergence warnings during training
warnings.filterwarnings("ignore", category=UserWarning)


# ── Labels for classification ──
LABEL_HOLD = 0
LABEL_BUY = 1
LABEL_SELL = 2


@dataclass
class AIStrategyConfig:
    """Configuration for AI-Integrated Strategy"""

    # Trade parameters
    lots: float = 0.01
    max_positions: int = 2

    # ML parameters
    min_training_samples: int = 100   # Min samples before model starts predicting
    retrain_interval: int = 50        # Retrain every N ticks
    confidence_threshold: float = 0.60  # Min prediction confidence to trade
    lookahead_bars: int = 10          # Bars to look ahead for labeling

    # Feature parameters
    ema_fast: int = 9
    ema_medium: int = 21
    ema_slow: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    momentum_short: int = 5
    momentum_long: int = 10

    # Labeling threshold (min price change % to label BUY/SELL vs HOLD)
    label_threshold_pct: float = 0.001  # 0.1% minimum move

    # ATR-based SL/TP
    atr_sl_multiplier: float = 1.5
    atr_tp_multiplier: float = 2.5

    # Point value
    point_value: float = 0.01

    # Fallback RSI thresholds (when model not ready)
    fallback_rsi_buy: float = 35.0
    fallback_rsi_sell: float = 65.0


# ── Production Presets ─────────────────────────────────────────────────────────
# Discovered via strategy_sweep.py on 3-month XAU/USD H1 data (Dec 2025 – Mar 2026)
# +12.1% return, 33 trades, 54.5% win rate, PF 1.17, Sharpe 1.16, Max DD 20.1%

BEST_XAU_H1 = AIStrategyConfig(
    lots=0.05,
    max_positions=2,
    min_training_samples=50,
    retrain_interval=20,
    confidence_threshold=0.55,
    atr_sl_multiplier=3.0,
    atr_tp_multiplier=4.0,
    lookahead_bars=10,
    label_threshold_pct=0.001,
    fallback_rsi_buy=35.0,
    fallback_rsi_sell=65.0,
)

# Conservative version — tighter confidence, smaller lots
CONSERVATIVE_XAU_H1 = AIStrategyConfig(
    lots=0.02,
    max_positions=1,
    min_training_samples=50,
    retrain_interval=20,
    confidence_threshold=0.60,
    atr_sl_multiplier=3.0,
    atr_tp_multiplier=4.0,
    lookahead_bars=10,
    label_threshold_pct=0.001,
    fallback_rsi_buy=30.0,
    fallback_rsi_sell=70.0,
)

# ── SCALPING PRESETS (M15 timeframe) ──────────────────────────────────────────
# Backtested on 2 months XAUUSD M15 data.
# NOTE: AI on M15 is not profitable yet (model needs more data to learn short patterns).
# Use SMCScalperStrategy with smc_scalper_best preset for M15 scalping instead.

# Aggressive scalping attempt — more entries, fast TP
AI_SCALP_AGGRESSIVE = AIStrategyConfig(
    lots=0.05,
    max_positions=2,
    min_training_samples=30,
    retrain_interval=10,
    confidence_threshold=0.45,
    atr_sl_multiplier=1.5,
    atr_tp_multiplier=2.5,
    lookahead_bars=5,
    label_threshold_pct=0.0005,
    fallback_rsi_buy=30.0,
    fallback_rsi_sell=70.0,
)

# Safe scalping — fewer entries, better quality signals
AI_SCALP_SAFE = AIStrategyConfig(
    lots=0.03,
    max_positions=1,
    min_training_samples=40,
    retrain_interval=15,
    confidence_threshold=0.55,
    atr_sl_multiplier=2.0,
    atr_tp_multiplier=3.0,
    lookahead_bars=5,
    label_threshold_pct=0.0005,
    fallback_rsi_buy=28.0,
    fallback_rsi_sell=72.0,
)


class AIStrategy(Strategy):
    """
    AI-Integrated Trading Strategy

    Uses a GradientBoosting classifier trained on technical indicator features
    to predict BUY/SELL/HOLD signals. The model self-trains from observed
    price movements and retrains periodically.

    Pipeline:
    1. Collect tick → store in price history
    2. Extract features (15+ indicators)
    3. If model is trained → predict with confidence
    4. If confidence > threshold → generate signal
    5. If model not ready → use fallback RSI+EMA rules
    6. Label past data when enough future bars available
    7. Retrain model periodically
    """

    def __init__(self, config: AIStrategyConfig = None):
        if config is None:
            config = AIStrategyConfig()
        super().__init__(config)

        # Price data
        self.closes: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []

        # ML components
        self.model = None
        self.is_trained = False
        self.is_training = False
        self.training_features: List[List[float]] = []
        self.training_labels: List[int] = []
        self.pending_labels: deque = deque(maxlen=5000)  # (tick_idx, features)
        
        # Concurrency
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=1)

        # Counters
        self.tick_count = 0
        self.ticks_since_retrain = 0
        self.total_predictions = 0
        self.correct_predictions = 0

        # Trading state
        self.last_signal = None
        self.bars_since_trade = 999

    def on_tick(
        self,
        price: float,
        bid: float,
        ask: float,
        positions: List[Position],
        timestamp: int = None,
    ) -> Optional[Dict]:
        self.tick_count += 1
        self.ticks_since_retrain += 1
        self.bars_since_trade += 1

        mid = (bid + ask) / 2
        self.closes.append(mid)
        self.highs.append(ask)
        self.lows.append(bid)

        # Keep bounded history
        max_len = 500
        if len(self.closes) > max_len:
            trim = len(self.closes) - max_len
            self.closes = self.closes[trim:]
            self.highs = self.highs[trim:]
            self.lows = self.lows[trim:]
            # Adjust pending labels indices
            new_pending = deque(maxlen=5000)
            for idx, feats in self.pending_labels:
                new_idx = idx - trim
                if new_idx >= 0:
                    new_pending.append((new_idx, feats))
            self.pending_labels = new_pending

        # Need minimum data for feature extraction
        min_bars = self.config.ema_slow + 10
        if len(self.closes) < min_bars:
            return None

        # ── Step 1: Label past data points ──
        self._label_pending_data()

        # ── Step 2: Extract current features ──
        features = self._extract_features()
        if features is None:
            return None

        # Store for future labeling
        self.pending_labels.append((len(self.closes) - 1, features))

        # ── Step 4: Retrain model periodically ──
        if (
            self.ticks_since_retrain >= self.config.retrain_interval
            and len(self.training_features) >= self.config.min_training_samples
            and not self.is_training
        ):
            self.ticks_since_retrain = 0
            # Start background training
            self.executor.submit(self._train_model)

        # ── Step 4: Manage existing positions ──
        action = self._manage_positions(positions, bid, ask)
        if action:
            return action

        # Check position limit
        if len(positions) >= self.config.max_positions:
            return None

        # Cooldown
        if self.bars_since_trade < 3:
            return None

        # ── Step 5: Predict or fallback ──
        if self.is_trained and self.model is not None:
            return self._predict_and_trade(features, bid, ask, positions)
        else:
            return self._fallback_trade(bid, ask, positions)

    def _extract_features(self) -> Optional[List[float]]:
        """Extract 15+ technical indicator features from price data."""
        closes = self.closes
        highs = self.highs
        lows = self.lows

        try:
            # ── EMAs ──
            ema_fast = calculate_ema(closes, self.config.ema_fast)
            ema_med = calculate_ema(closes, self.config.ema_medium)
            ema_slow = calculate_ema(closes, self.config.ema_slow)

            if any(x is None for x in [ema_fast, ema_med, ema_slow]):
                return None

            price = closes[-1]

            # ── RSI ──
            rsi = calculate_rsi(closes, self.config.rsi_period)
            if rsi is None:
                rsi = 50.0

            # ── ATR ──
            atr = calculate_atr(highs, lows, closes, self.config.atr_period)
            if atr is None or atr == 0:
                atr = abs(highs[-1] - lows[-1]) or 0.01

            # ── Bollinger Bands ──
            bb = calculate_bollinger_bands(closes, self.config.bb_period, self.config.bb_std)
            if bb is not None:
                upper_bb, middle_bb, lower_bb = bb
                bb_width = (upper_bb - lower_bb) / middle_bb if middle_bb > 0 else 0
                bb_pct_b = (price - lower_bb) / (upper_bb - lower_bb) if (upper_bb - lower_bb) > 0 else 0.5
            else:
                bb_width = 0
                bb_pct_b = 0.5

            # ── MACD (manual for proper history) ──
            ema12 = calculate_ema(closes, 12)
            ema26 = calculate_ema(closes, 26)
            if ema12 is not None and ema26 is not None:
                macd_line = ema12 - ema26
                macd_normalized = macd_line / price if price > 0 else 0
            else:
                macd_normalized = 0

            # ── Momentum ──
            mom_short = (price - closes[-self.config.momentum_short]) / closes[-self.config.momentum_short] if len(closes) >= self.config.momentum_short else 0
            mom_long = (price - closes[-self.config.momentum_long]) / closes[-self.config.momentum_long] if len(closes) >= self.config.momentum_long else 0

            # ── Price relative to EMAs ──
            dist_ema_fast = (price - ema_fast) / price if price > 0 else 0
            dist_ema_med = (price - ema_med) / price if price > 0 else 0
            dist_ema_slow = (price - ema_slow) / price if price > 0 else 0

            # ── EMA alignment score ──
            ema_bullish = 1.0 if ema_fast > ema_med > ema_slow else 0.0
            ema_bearish = 1.0 if ema_fast < ema_med < ema_slow else 0.0

            # ── Volatility ratio ──
            atr_ratio = atr / price if price > 0 else 0

            # ── Recent high/low range ──
            if len(closes) >= 20:
                recent_high = max(highs[-20:])
                recent_low = min(lows[-20:])
                range_position = (price - recent_low) / (recent_high - recent_low) if (recent_high - recent_low) > 0 else 0.5
            else:
                range_position = 0.5

            # ── Candle body ratio ──
            body = abs(closes[-1] - closes[-2]) if len(closes) >= 2 else 0
            wick = (highs[-1] - lows[-1]) if (highs[-1] - lows[-1]) > 0 else 0.01
            body_ratio = body / wick

            features = [
                rsi / 100.0,                # 0: RSI normalized (0-1)
                dist_ema_fast,              # 1: Price distance from fast EMA
                dist_ema_med,               # 2: Price distance from medium EMA
                dist_ema_slow,              # 3: Price distance from slow EMA
                ema_bullish,                # 4: EMA bullish alignment
                ema_bearish,                # 5: EMA bearish alignment
                bb_pct_b,                   # 6: BB %B (position within bands)
                bb_width,                   # 7: BB width (volatility)
                macd_normalized,            # 8: MACD normalized
                mom_short,                  # 9: Short momentum
                mom_long,                   # 10: Long momentum
                atr_ratio,                  # 11: ATR ratio (volatility)
                range_position,             # 12: Position in recent range
                body_ratio,                 # 13: Candle body ratio
                1.0 if closes[-1] > closes[-2] else 0.0,  # 14: Last candle bullish
            ]

            return features

        except (IndexError, ZeroDivisionError, ValueError):
            return None

    def _label_pending_data(self):
        """Label past data points based on future price movement."""
        labeled = []

        for idx, features in self.pending_labels:
            future_idx = idx + self.config.lookahead_bars

            # Check if we have enough future data
            if future_idx >= len(self.closes):
                break

            # Calculate future return
            current_price = self.closes[idx]
            future_price = self.closes[future_idx]

            if current_price == 0:
                labeled.append((idx, features))
                continue

            future_return = (future_price - current_price) / current_price

            # Label based on threshold
            if future_return > self.config.label_threshold_pct:
                label = LABEL_BUY
            elif future_return < -self.config.label_threshold_pct:
                label = LABEL_SELL
            else:
                label = LABEL_HOLD

            self.training_features.append(features)
            self.training_labels.append(label)
            labeled.append((idx, features))

        # Remove labeled items
        for item in labeled:
            try:
                self.pending_labels.remove(item)
            except ValueError:
                pass

        # Keep training data bounded
        max_samples = 2000
        if len(self.training_features) > max_samples:
            self.training_features = self.training_features[-max_samples:]
            self.training_labels = self.training_labels[-max_samples:]

    def _train_model(self):
        """Train or retrain the GradientBoosting model in a background thread."""
        if self.is_training:
            return
            
        self.is_training = True
        try:
            from sklearn.ensemble import GradientBoostingClassifier

            # Deep copy to avoid thread mutation issues
            X = np.array(self.training_features.copy())
            y = np.array(self.training_labels.copy())

            # Check class distribution - need at least 2 classes
            unique_classes = np.unique(y)
            if len(unique_classes) < 2:
                self.is_training = False
                return

            new_model = GradientBoostingClassifier(
                n_estimators=50,
                max_depth=4,
                learning_rate=0.1,
                min_samples_split=10,
                min_samples_leaf=5,
                subsample=0.8,
                random_state=42,
            )

            new_model.fit(X, y)
            
            # Hot swap
            self.model = new_model
            self.is_trained = True
            logger.debug("AI Model retrained successfully in background.")

        except Exception as e:
            logger.debug(f"Failed to train AI model: {e}")
        finally:
            self.is_training = False

    def _predict_and_trade(
        self,
        features: List[float],
        bid: float,
        ask: float,
        positions: List[Position],
    ) -> Optional[Dict]:
        """Use ML model to predict and potentially trade."""
        try:
            X = np.array([features])
            prediction = self.model.predict(X)[0]
            probabilities = self.model.predict_proba(X)[0]
            confidence = max(probabilities)

            self.total_predictions += 1

            # Only trade on high confidence
            if confidence < self.config.confidence_threshold:
                return None

            # Calculate ATR-based SL/TP
            atr = calculate_atr(self.highs, self.lows, self.closes, self.config.atr_period)
            if atr is None or atr <= 0:
                atr = abs(self.highs[-1] - self.lows[-1]) or 0.5

            sl_dist = atr * self.config.atr_sl_multiplier
            tp_dist = atr * self.config.atr_tp_multiplier

            if prediction == LABEL_BUY:
                if not any(p.side == PositionSide.LONG for p in positions):
                    self.bars_since_trade = 0
                    self.last_signal = "BUY"
                    return {
                        "action": "open",
                        "side": OrderSide.BUY,
                        "amount": self.config.lots,
                        "sl": round(bid - sl_dist, 2),
                        "tp": round(ask + tp_dist, 2),
                    }

            elif prediction == LABEL_SELL:
                if not any(p.side == PositionSide.SHORT for p in positions):
                    self.bars_since_trade = 0
                    self.last_signal = "SELL"
                    return {
                        "action": "open",
                        "side": OrderSide.SELL,
                        "amount": self.config.lots,
                        "sl": round(ask + sl_dist, 2),
                        "tp": round(bid - tp_dist, 2),
                    }

        except Exception as e:
            logger.debug(f"Predict and trade failed: {e}")

        return None

    def _fallback_trade(
        self,
        bid: float,
        ask: float,
        positions: List[Position],
    ) -> Optional[Dict]:
        """Fallback: simple RSI + EMA rules when model isn't ready."""
        rsi = calculate_rsi(self.closes, self.config.rsi_period)
        if rsi is None:
            return None

        ema_fast = calculate_ema(self.closes, self.config.ema_fast)
        ema_slow = calculate_ema(self.closes, self.config.ema_slow)
        if ema_fast is None or ema_slow is None:
            return None

        atr = calculate_atr(self.highs, self.lows, self.closes, self.config.atr_period)
        if atr is None or atr <= 0:
            atr = abs(self.highs[-1] - self.lows[-1]) or 0.5

        sl_dist = atr * self.config.atr_sl_multiplier
        tp_dist = atr * self.config.atr_tp_multiplier

        # Buy: RSI oversold + EMA bullish
        if rsi < self.config.fallback_rsi_buy and ema_fast > ema_slow:
            if not any(p.side == PositionSide.LONG for p in positions):
                self.bars_since_trade = 0
                self.last_signal = "BUY (fallback)"
                return {
                    "action": "open",
                    "side": OrderSide.BUY,
                    "amount": self.config.lots,
                    "sl": round(bid - sl_dist, 2),
                    "tp": round(ask + tp_dist, 2),
                }

        # Sell: RSI overbought + EMA bearish
        if rsi > self.config.fallback_rsi_sell and ema_fast < ema_slow:
            if not any(p.side == PositionSide.SHORT for p in positions):
                self.bars_since_trade = 0
                self.last_signal = "SELL (fallback)"
                return {
                    "action": "open",
                    "side": OrderSide.SELL,
                    "amount": self.config.lots,
                    "sl": round(ask + sl_dist, 2),
                    "tp": round(bid - tp_dist, 2),
                }

        return None

    def _manage_positions(
        self, positions: List[Position], bid: float, ask: float
    ) -> Optional[Dict]:
        """Manage positions with TP/SL checking."""
        for pos in positions:
            if pos.tp:
                if pos.side == PositionSide.LONG and bid >= pos.tp:
                    return {"action": "close", "position_id": pos.id}
                if pos.side == PositionSide.SHORT and ask <= pos.tp:
                    return {"action": "close", "position_id": pos.id}

            if pos.sl:
                if pos.side == PositionSide.LONG and bid <= pos.sl:
                    return {"action": "close", "position_id": pos.id}
                if pos.side == PositionSide.SHORT and ask >= pos.sl:
                    return {"action": "close", "position_id": pos.id}

        return None

    def get_stats(self) -> Dict:
        """Get AI strategy statistics."""
        accuracy = (
            (self.correct_predictions / self.total_predictions * 100)
            if self.total_predictions > 0
            else 0
        )
        return {
            "model_trained": self.is_trained,
            "training_samples": len(self.training_features),
            "total_predictions": self.total_predictions,
            "accuracy": round(accuracy, 1),
            "last_signal": self.last_signal,
            "tick_count": self.tick_count,
        }
