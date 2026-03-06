"""
HFT Strategy Parameter Optimizer
Uses grid search to find optimal parameters
"""

import itertools
import time
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json

import pandas as pd

from trading_bot.strategy.hft import HFTStrategy, HFTConfig
from trading_bot.core.backtest_engine import BacktestEngine


@dataclass
class OptimizationResult:
    """Result of a single parameter combination test"""

    params: HFTConfig
    total_return_pct: float
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    score: float  # Composite score for ranking


class HFTParameterOptimizer:
    """
    Grid search optimizer for HFT strategy parameters

    Tests all combinations of specified parameter ranges
    and returns the best performing configuration.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        initial_balance: float = 10000.0,
        results_dir: str = "./optimization_results",
    ):
        self.data = data
        self.initial_balance = initial_balance
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True, parents=True)
        self.results: List[OptimizationResult] = []

    def optimize(
        self,
        param_ranges: Dict[str, List[Any]] = None,
        top_n: int = 10,
    ) -> List[OptimizationResult]:
        """
        Run grid search optimization

        Args:
            param_ranges: Dictionary of parameter names and value ranges
            top_n: Return top N results

        Returns:
            List of top performing parameter combinations
        """
        if param_ranges is None:
            # Default parameter ranges to test
            param_ranges = {
                "profit_target_pips": [2, 3, 5, 8],
                "stop_loss_pips": [3, 5, 7, 10],
                "momentum_threshold": [0.0001, 0.0002, 0.0003],
                "max_hold_seconds": [15, 30, 60],
                "min_volatility": [0.00005, 0.0001, 0.0002],
                "max_volatility": [0.0005, 0.001, 0.002],
            }

        # Generate all parameter combinations
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)

        print(f"🔍 Running grid search with {total_combinations} combinations...")
        print("=" * 70)

        # Test each combination
        combination_num = 0
        for values in itertools.product(*param_values):
            combination_num += 1

            # Create config with current parameters
            config_kwargs = dict(zip(param_names, values))
            config = HFTConfig(**config_kwargs)

            # Run backtest
            result = self._test_config(config)

            if result:
                self.results.append(result)

                if combination_num % 10 == 0 or combination_num == total_combinations:
                    progress = (combination_num / total_combinations) * 100
                    print(
                        f"  Progress: {combination_num}/{total_combinations} ({progress:.1f}%) - "
                        f"Best score: {max(self.results, key=lambda x: x.score).score:.2f}"
                    )

        # Sort by score and return top N
        self.results.sort(key=lambda x: x.score, reverse=True)
        top_results = self.results[:top_n]

        # Save results
        self._save_results(top_results)

        # Print summary
        self._print_summary(top_results)

        return top_results

    def _test_config(self, config: HFTConfig) -> OptimizationResult:
        """Test a single parameter configuration"""
        try:
            # Create backtest engine
            engine = BacktestEngine(
                initial_balance=self.initial_balance,
                leverage=200,
                spread=0.02,
                commission=0,
                slippage=0.01,
            )

            # Create strategy
            strategy = HFTStrategy(config)

            # Run backtest
            result = engine.run(
                strategy=strategy,
                data=self.data,
                symbol="XAUUSD",
            )

            # Calculate composite score
            # Weights: Return (40%), Win Rate (20%), Profit Factor (20%), Drawdown (20%)
            score = (
                result.total_return_pct * 0.4
                + (result.win_rate - 50) * 0.2  # Normalize around 50%
                + (result.profit_factor - 1) * 10 * 0.2  # Scale PF
                + (-result.max_drawdown_pct) * 0.2  # Lower drawdown is better
            )

            return OptimizationResult(
                params=config,
                total_return_pct=result.total_return_pct,
                total_trades=result.total_trades,
                win_rate=result.win_rate,
                profit_factor=result.profit_factor,
                max_drawdown_pct=result.max_drawdown_pct,
                sharpe_ratio=result.sharpe_ratio,
                score=score,
            )

        except Exception as e:
            print(f"  ❌ Error testing config: {e}")
            return None

    def _save_results(self, top_results: List[OptimizationResult]):
        """Save optimization results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.results_dir / f"hft_optimization_{timestamp}.json"

        results_data = [
            {
                "rank": i + 1,
                "params": asdict(r.params),
                "total_return_pct": r.total_return_pct,
                "total_trades": r.total_trades,
                "win_rate": r.win_rate,
                "profit_factor": r.profit_factor,
                "max_drawdown_pct": r.max_drawdown_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "score": r.score,
            }
            for i, r in enumerate(top_results)
        ]

        with open(output_file, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\n💾 Results saved: {output_file}")

    def _print_summary(self, top_results: List[OptimizationResult]):
        """Print optimization summary"""
        print("\n" + "=" * 80)
        print("🏆 TOP 10 HFT PARAMETER COMBINATIONS")
        print("=" * 80)

        print(
            f"{'Rank':<6}{'Return %':<12}{'Trades':<10}{'Win Rate':<12}{'PF':<8}{'Max DD':<10}{'Score':<10}"
        )
        print("-" * 80)

        for i, r in enumerate(top_results, 1):
            print(
                f"{i:<6}"
                f"{r.total_return_pct:>8.2f}%  "
                f"{r.total_trades:<10}"
                f"{r.win_rate:>8.1f}%  "
                f"{r.profit_factor:>6.2f}  "
                f"{r.max_drawdown_pct:>7.2f}% "
                f"{r.score:>8.2f}"
            )

        print("=" * 80)

        # Print best parameters
        best = top_results[0]
        print("\n🎯 BEST PARAMETERS:")
        for key, value in asdict(best.params).items():
            if not key.startswith("_"):
                print(f"  {key}: {value}")

        print(f"\n  Expected Return: {best.total_return_pct:.2f}%")
        print(f"  Expected Win Rate: {best.win_rate:.1f}%")
        print(f"  Profit Factor: {best.profit_factor:.2f}")


def run_hft_optimization(
    data_file: str = "data/XAUUSD_1m.csv",
    output_dir: str = "./optimization_results",
):
    """
    Run HFT strategy parameter optimization

    Usage:
        from trading_bot.core.hft_optimizer import run_hft_optimization
        run_hft_optimization()
    """
    print("🚀 Starting HFT Parameter Optimization")
    print("=" * 70)

    # Load data
    if not Path(data_file).exists():
        print(f"❌ Data file not found: {data_file}")
        return

    df = pd.read_csv(data_file)
    print(f"📊 Loaded {len(df)} rows of data")

    # Create optimizer
    optimizer = HFTParameterOptimizer(
        data=df,
        initial_balance=10000.0,
        results_dir=output_dir,
    )

    # Run optimization
    top_results = optimizer.optimize(top_n=10)

    print("\n✅ Optimization complete!")
    return top_results


if __name__ == "__main__":
    run_hft_optimization()
