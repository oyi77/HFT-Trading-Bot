"""
Unified Backtest Framework
Run backtests across all strategies and compare performance across providers
"""

import json
import time
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import pandas as pd

from trading_bot.strategy.base import Strategy
from trading_bot.strategy import (
    XAUHedgingStrategy,
    XAUHedgingConfig,
    GridStrategy,
    GridConfig,
    TrendStrategy,
    TrendConfig,
    HFTStrategy,
    HFTConfig,
    NFIStrategy,
    NFIConfig,
    IBBreakoutStrategy,
    IBBreakoutConfig,
    SevenCandleStrategy,
    SevenCandleConfig,
    BBMacdRsiStrategy,
    BBMacdRsiConfig,
    AIStrategy,
    AIStrategyConfig,
)
from trading_bot.strategy.scalping import ScalpingStrategy, ScalpingConfig
from trading_bot.exchange.base import Exchange
from trading_bot.exchange.simulator import SimulatorExchange
from trading_bot.core.backtest_engine import BacktestEngine, BacktestResult


@dataclass
class StrategyBacktestConfig:
    """Configuration for a single strategy backtest"""

    strategy_name: str
    strategy_class: Type[Strategy]
    config: Any
    symbols: List[str] = field(default_factory=lambda: ["XAUUSDm"])
    timeframes: List[str] = field(default_factory=lambda: ["1m"])


@dataclass
class ProviderConfig:
    """Configuration for different exchange providers"""

    name: str
    spread: float  # Spread in price units
    commission: float  # Per lot
    slippage: float  # Price slippage
    leverage: int
    margin_requirement: float  # 0.5 = 200:1 leverage
    execution_delay_ms: int  # Execution delay in milliseconds

    # Provider-specific fees
    overnight_fee_long: float = 0.0  # Overnight holding fee
    overnight_fee_short: float = 0.0
    withdrawal_fee: float = 0.0


# Provider configurations
PROVIDERS = {
    "simulator": ProviderConfig(
        name="Simulator",
        spread=0.02,  # $0.02 for XAU/USD
        commission=0,
        slippage=0.01,
        leverage=200,
        margin_requirement=0.005,
        execution_delay_ms=0,
    ),
    "ostium": ProviderConfig(
        name="Ostium DEX",
        spread=0.05,  # Higher spread for DEX
        commission=0.001,  # 0.1% commission
        slippage=0.03,  # Higher slippage on DEX
        leverage=100,
        margin_requirement=0.01,
        execution_delay_ms=500,  # Slower execution on blockchain
    ),
    "exness": ProviderConfig(
        name="Exness",
        spread=0.015,  # Tight spread
        commission=0,
        slippage=0.005,  # Low slippage
        leverage=2000,  # Very high leverage
        margin_requirement=0.0005,
        execution_delay_ms=50,  # Fast execution
        overnight_fee_long=-2.5,  # Swap fees
        overnight_fee_short=-2.5,
    ),
    "bybit": ProviderConfig(
        name="Bybit",
        spread=0.025,
        commission=0.0006,  # 0.06% taker fee
        slippage=0.015,
        leverage=100,
        margin_requirement=0.01,
        execution_delay_ms=100,
    ),
}


@dataclass
class ProviderBacktestResult:
    """Backtest result for a specific provider + strategy combination"""

    provider: str
    strategy: str
    symbol: str
    timeframe: str
    result: BacktestResult
    execution_time: float
    provider_config: ProviderConfig = None


@dataclass
class ComparisonReport:
    """Comprehensive comparison report across all strategies and providers"""

    timestamp: str
    results: List[ProviderBacktestResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert report to dictionary"""
        return {
            "timestamp": self.timestamp,
            "results": [
                {
                    "provider": r.provider,
                    "strategy": r.strategy,
                    "symbol": r.symbol,
                    "timeframe": r.timeframe,
                    "execution_time": r.execution_time,
                    "result": {
                        "total_return_pct": r.result.total_return_pct,
                        "total_trades": r.result.total_trades,
                        "win_rate": r.result.win_rate,
                        "profit_factor": r.result.profit_factor,
                        "max_drawdown_pct": r.result.max_drawdown_pct,
                        "sharpe_ratio": r.result.sharpe_ratio,
                        "avg_trade": r.result.avg_trade,
                    },
                }
                for r in self.results
            ],
        }


class UnifiedBacktestRunner:
    """
    Unified backtest runner for all strategies across all providers

    Features:
    - Run multiple strategies: XAU Hedging, Grid, Trend, HFT
    - Test across providers: Simulator, Ostium, Exness, Bybit (using data)
    - Generate comparison reports
    - Rank strategies by performance metrics
    """

    def __init__(
        self,
        data_dir: str = "./data",
        results_dir: str = "./backtest_results",
        initial_balance: float = 10000.0,
    ):
        self.data_dir = Path(data_dir)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True, parents=True)
        self.initial_balance = initial_balance

        # Strategy configurations
        self.strategy_configs: List[StrategyBacktestConfig] = [
            StrategyBacktestConfig(
                strategy_name="XAU_Hedging",
                strategy_class=XAUHedgingStrategy,
                config=XAUHedgingConfig(lots=0.01, stop_loss=500, take_profit=1000),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h", "1d"],
            ),
            StrategyBacktestConfig(
                strategy_name="Grid",
                strategy_class=GridStrategy,
                config=GridConfig(lots=0.01, grid_levels=5, grid_spacing_pct=0.005),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h"],
            ),
            StrategyBacktestConfig(
                strategy_name="Trend",
                strategy_class=TrendStrategy,
                config=TrendConfig(
                    lots=0.01, ema_fast=9, ema_slow=21, stop_loss_pips=50
                ),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h"],
            ),
            StrategyBacktestConfig(
                strategy_name="HFT",
                strategy_class=HFTStrategy,
                config=HFTConfig(lots=0.01, profit_target_pips=10, stop_loss_pips=8),
                symbols=["XAUUSDm"],
                timeframes=["5m", "15m"],
            ),
            StrategyBacktestConfig(
                strategy_name="NFI_Normal",
                strategy_class=NFIStrategy,
                config=NFIConfig(lots=0.01, mode="normal"),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h"],
            ),
            StrategyBacktestConfig(
                strategy_name="NFI_Scalp",
                strategy_class=NFIStrategy,
                config=NFIConfig(lots=0.01, mode="scalp"),
                symbols=["XAUUSDm"],
                timeframes=["5m", "15m"],
            ),
            StrategyBacktestConfig(
                strategy_name="IB_Breakout",
                strategy_class=IBBreakoutStrategy,
                config=IBBreakoutConfig(lots=0.01),
                symbols=["XAUUSDm"],
                timeframes=["1h"],
            ),
            StrategyBacktestConfig(
                strategy_name="Scalping",
                strategy_class=ScalpingStrategy,
                config=ScalpingConfig(lots=0.01),
                symbols=["XAUUSDm"],
                timeframes=["5m", "15m"],
            ),
            StrategyBacktestConfig(
                strategy_name="SevenCandle",
                strategy_class=SevenCandleStrategy,
                config=SevenCandleConfig(lots=0.01),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h"],
            ),
            StrategyBacktestConfig(
                strategy_name="BB_MACD_RSI",
                strategy_class=BBMacdRsiStrategy,
                config=BBMacdRsiConfig(lots=0.01),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h"],
            ),
            StrategyBacktestConfig(
                strategy_name="AI_Strategy",
                strategy_class=AIStrategy,
                config=AIStrategyConfig(lots=0.01, min_training_samples=50, retrain_interval=25),
                symbols=["XAUUSDm"],
                timeframes=["1h", "4h"],
            ),
        ]

    def run_all_backtests(
        self,
        providers: List[str] = None,
        strategies: List[str] = None,
        data_file: Optional[str] = None,
    ) -> ComparisonReport:
        """
        Run backtests for all specified strategies across all providers

        Args:
            providers: List of providers to test ['simulator', 'all']
            strategies: List of strategy names to test (None = all)
            data_file: Path to historical data file (OHLCV CSV)

        Returns:
            ComparisonReport with all results
        """
        if providers is None:
            providers = ["simulator"]

        report = ComparisonReport(timestamp=datetime.now().isoformat())

        # Load data once
        data = self._load_data(data_file)
        if data is None:
            print("❌ No data available for backtest")
            return report

        total_tests = len(providers) * len(self.strategy_configs)
        test_num = 0

        for provider in providers:
            for strat_config in self.strategy_configs:
                test_num += 1

                # Filter strategies if specified
                if strategies and strat_config.strategy_name not in strategies:
                    continue

                print(f"\n{'=' * 60}")
                print(
                    f"🧪 Test {test_num}/{total_tests}: {strat_config.strategy_name} on {provider}"
                )
                print(f"{'=' * 60}")

                for symbol in strat_config.symbols:
                    for timeframe in strat_config.timeframes:
                        result = self._run_single_backtest(
                            provider=provider,
                            strat_config=strat_config,
                            symbol=symbol,
                            timeframe=timeframe,
                            data=data,
                        )
                        if result:
                            report.results.append(result)

        # Save report
        self._save_report(report)

        # Print summary
        self._print_comparison_summary(report)

        return report

    def _run_single_backtest(
        self,
        provider: str,
        strat_config: StrategyBacktestConfig,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
    ) -> Optional[ProviderBacktestResult]:
        """Run a single backtest with provider-specific configuration"""
        try:
            start_time = time.time()

            # Get provider configuration
            provider_config = PROVIDERS.get(provider, PROVIDERS["simulator"])

            # Create strategy instance
            strategy = strat_config.strategy_class(strat_config.config)

            # Create backtest engine with provider-specific settings
            engine = BacktestEngine(
                initial_balance=self.initial_balance,
                leverage=provider_config.leverage,
                spread=provider_config.spread,
                commission=provider_config.commission,
                slippage=provider_config.slippage,
            )

            # Simulate execution delay if specified
            if provider_config.execution_delay_ms > 0:
                time.sleep(provider_config.execution_delay_ms / 1000.0)

            # Run backtest
            result = engine.run(
                strategy=strategy,
                data=data,
                symbol=symbol,
            )

            execution_time = time.time() - start_time

            print(f"  ✅ {strat_config.strategy_name} | {symbol} | {timeframe}")
            print(
                f"     Return: {result.total_return_pct:.2f}% | Trades: {result.total_trades} | Win Rate: {result.win_rate:.1f}% | Max DD: {result.max_drawdown_pct:.2f}%"
            )

            return ProviderBacktestResult(
                provider=provider,
                strategy=strat_config.strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                result=result,
                execution_time=execution_time,
                provider_config=provider_config,
            )

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _load_data(self, data_file: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Load historical data for backtest"""
        if data_file:
            file_path = Path(data_file)
        else:
            # Try to find default data file
            file_path = self.data_dir / "XAUUSD_1m.csv"

        if not file_path.exists():
            print(f"⚠️ Data file not found: {file_path}")
            print("Generating sample data for testing...")
            return self._generate_sample_data()

        try:
            df = pd.read_csv(file_path)
            # Ensure required columns
            required = ["timestamp", "open", "high", "low", "close", "volume"]
            for col in required:
                if col not in df.columns:
                    print(f"❌ Missing column: {col}")
                    return None
            return df
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return self._generate_sample_data()

    def _generate_sample_data(self, rows: int = 10000) -> pd.DataFrame:
        """Generate sample OHLCV data for testing"""
        print(f"📊 Generating {rows} rows of sample data...")

        import numpy as np

        np.random.seed(42)
        base_price = 2650.0

        timestamps = pd.date_range(end=datetime.now(), periods=rows, freq="1min")

        # Generate random walk prices
        returns = np.random.normal(0.0001, 0.001, rows)
        prices = base_price * np.exp(np.cumsum(returns))

        # Generate OHLC from close
        data = []
        for i, (ts, close) in enumerate(zip(timestamps, prices)):
            volatility = close * 0.0005
            open_price = close + np.random.normal(0, volatility * 0.3)
            high = max(open_price, close) + abs(np.random.normal(0, volatility * 0.5))
            low = min(open_price, close) - abs(np.random.normal(0, volatility * 0.5))
            volume = np.random.randint(100, 1000)

            data.append(
                {
                    "timestamp": int(ts.timestamp() * 1000),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                }
            )

        return pd.DataFrame(data)

    def _save_report(self, report: ComparisonReport):
        """Save comparison report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.results_dir / f"backtest_comparison_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        print(f"\n💾 Report saved: {report_file}")

    def _print_comparison_summary(self, report: ComparisonReport):
        """Print comparison summary table"""
        print("\n" + "=" * 80)
        print("📊 BACKTEST COMPARISON SUMMARY")
        print("=" * 80)

        if not report.results:
            print("No results to display")
            return

        # Sort by total return
        sorted_results = sorted(
            report.results, key=lambda x: x.result.total_return_pct, reverse=True
        )

        # Header
        print(
            f"{'Rank':<6}{'Strategy':<15}{'Provider':<12}{'Return %':<12}{'Trades':<10}{'Win Rate':<12}{'Max DD':<10}"
        )
        print("-" * 80)

        # Results
        for i, r in enumerate(sorted_results[:10], 1):
            print(
                f"{i:<6}"
                f"{r.strategy:<15}"
                f"{r.provider:<12}"
                f"{r.result.total_return_pct:>8.2f}%  "
                f"{r.result.total_trades:<10}"
                f"{r.result.win_rate:>8.1f}%  "
                f"{r.result.max_drawdown_pct:>7.2f}%"
            )

        print("=" * 80)

        # Best performers
        print("\n🏆 TOP PERFORMERS:")
        best_return = sorted_results[0]
        best_wr = max(report.results, key=lambda x: x.result.win_rate)
        best_dd = min(report.results, key=lambda x: x.result.max_drawdown_pct)
        best_pf = max(report.results, key=lambda x: x.result.profit_factor)

        print(
            f"  Best Return: {best_return.strategy} on {best_return.provider} ({best_return.result.total_return_pct:.2f}%)"
        )
        print(
            f"  Best Win Rate: {best_wr.strategy} on {best_wr.provider} ({best_wr.result.win_rate:.1f}%)"
        )
        print(
            f"  Lowest Drawdown: {best_dd.strategy} on {best_dd.provider} ({best_dd.result.max_drawdown_pct:.2f}%)"
        )
        print(
            f"  Best Profit Factor: {best_pf.strategy} on {best_pf.provider} ({best_pf.result.profit_factor:.2f})"
        )

        # Provider comparison
        print("\n📊 PROVIDER COMPARISON:")
        providers_used = set(r.provider for r in report.results)
        for provider in providers_used:
            provider_results = [r for r in report.results if r.provider == provider]
            avg_return = sum(r.result.total_return_pct for r in provider_results) / len(
                provider_results
            )
            avg_trades = sum(r.result.total_trades for r in provider_results) / len(
                provider_results
            )
            print(
                f"  {provider:<12}: Avg Return {avg_return:>7.2f}% | Avg Trades {avg_trades:.0f}"
            )


def run_strategy_comparison(
    data_file: Optional[str] = None,
    strategies: List[str] = None,
    providers: List[str] = None,
    output_dir: str = "./backtest_results",
):
    """
    Run comprehensive strategy comparison across multiple providers

    Args:
        data_file: Path to OHLCV CSV data file
        strategies: List of strategy names to test (None = all)
        providers: List of providers to test ['simulator', 'ostium', 'exness', 'bybit', 'all']
        output_dir: Directory to save results

    Example:
        # Test all strategies on all providers
        run_strategy_comparison()

        # Test specific strategies on specific providers
        run_strategy_comparison(strategies=["HFT", "XAU_Hedging"], providers=["exness", "ostium"])

        # Test on all providers
        run_strategy_comparison(providers=["all"])
    """
    # Handle provider selection
    if providers is None:
        providers = ["simulator"]
    elif "all" in providers:
        providers = ["simulator", "ostium", "exness", "bybit"]

    print(f"🎯 Testing on providers: {', '.join(providers)}")

    runner = UnifiedBacktestRunner(
        results_dir=output_dir,
        initial_balance=10000.0,
    )

    report = runner.run_all_backtests(
        providers=providers,
        strategies=strategies,
        data_file=data_file,
    )

    return report


if __name__ == "__main__":
    # Run comparison when executed directly
    print("🚀 Starting Unified Strategy Comparison")
    print("=" * 60)

    report = run_strategy_comparison()

    print("\n✅ Comparison complete!")
