"""
Backtest XAU Hedging Strategy with REAL data from yfinance
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.strategy.xau_hedging import XAUHedgingStrategy
from trading_bot.core.models import Config
# from trading_bot.exchange.simulator import SimulatorExchange  # Not needed for simple version
from fetch_xau_data import fetch_xau_data


def load_or_fetch_data(
    data_file: str = "data/xauusd_1y_1m.csv",
    force_fetch: bool = False
) -> pd.DataFrame:
    """Load local data or fetch from yfinance"""
    
    data_path = Path(data_file)
    
    if not force_fetch and data_path.exists():
        print(f"📂 Loading existing data from {data_file}")
        df = pd.read_csv(data_file)
        return df
    
    # Fetch new data
    print("🌐 Fetching fresh data from Yahoo Finance...")
    df = fetch_xau_data(period="1y", interval="1m", output_file=data_file)
    return df


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare data for backtesting"""
    
    # Ensure required columns exist
    if "timestamp" not in df.columns:
        for col in ["Datetime", "datetime", "Date", "date"]:
            if col in df.columns:
                df["timestamp"] = pd.to_datetime(df[col]).astype(int) // 10**6
                break
    
    # Rename columns if needed
    col_map = {
        "Open": "open", "open": "open",
        "High": "high", "high": "high",
        "Low": "low", "low": "low",
        "Close": "close", "close": "close",
    }
    df = df.rename(columns=col_map)
    
    # Also map single letter columns
    single_map = {"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    df = df.rename(columns=single_map)
    
    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    return df


class SimpleBacktester:
    """Simple backtester for XAU strategy"""
    
    def __init__(self, initial_balance=10000):
        self.balance = initial_balance
        self.positions = []
        self.trades = []
        self.point = 0.01  # XAU/USD
        self.contract_size = 100  # Standard lot
        
    def open_position(self, side, entry_price, volume, sl=None):
        """Open a position"""
        pos = {
            "id": len(self.trades),
            "side": side,
            "entry": entry_price,
            "volume": volume,
            "sl": sl,
            "open_time": None
        }
        self.positions.append(pos)
        return pos["id"]
    
    def close_position(self, pos, exit_price, reason=""):
        """Close a position"""
        if pos["side"] == "long":
            pips = (exit_price - pos["entry"]) / self.point
        else:
            pips = (pos["entry"] - exit_price) / self.point
        
        # Profit in dollars
        profit = pips * pos["volume"] * self.contract_size * self.point
        
        self.balance += profit
        
        self.trades.append({
            "side": pos["side"],
            "entry": pos["entry"],
            "exit": exit_price,
            "volume": pos["volume"],
            "profit": profit,
            "pips": pips,
            "reason": reason
        })
        
        self.positions.remove(pos)
        return profit
    
    def close_all(self, price):
        """Close all positions"""
        for pos in list(self.positions):
            self.close_position(pos, price, "end_of_test")


def run_real_backtest(
    data_file: str = "data/xauusd_1y_1m.csv",
    balance: float = 10000,
    lots: float = 0.02,
    stop_loss: int = 800,
    trailing: int = 200,
    x_distance: int = 100,
    max_spread: int = 50,
    fetch: bool = False
):
    """
    Run backtest with real XAU/USD data
    """
    print("=" * 60)
    print("🥇 XAU/USD BACKTEST WITH REAL DATA")
    print("=" * 60)
    
    # Load data
    df = load_or_fetch_data(data_file, force_fetch=fetch)
    df = prepare_data(df)
    
    if df.empty:
        print("❌ No data available!")
        return
    
    print(f"\n📊 Data loaded: {len(df)} candles")
    print(f"   Period: {len(df) // (24 * 60)} days")
    print(f"   Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
    
    # Simple backtester
    bt = SimpleBacktester(balance)
    
    # Config
    trail_start = stop_loss + 100  # Start trailing after BE + buffer
    
    print("\n🚀 Running backtest...")
    print(f"   Initial balance: ${balance:,.2f}")
    print(f"   Lots: {lots}")
    print(f"   Stop Loss: {stop_loss} pts")
    print(f"   Trailing: {trailing} pts")
    print()
    
    trade_count = 0
    last_report = 0
    
    for i, row in df.iterrows():
        price = row["close"]
        bid = price - 0.02
        ask = price + 0.02
        timestamp = row["timestamp"]
        
        # Check SL for existing positions
        for pos in list(bt.positions):
            if pos["sl"]:
                if pos["side"] == "long" and row["low"] <= pos["sl"]:
                    bt.close_position(pos, pos["sl"], "sl")
                elif pos["side"] == "short" and row["high"] >= pos["sl"]:
                    bt.close_position(pos, pos["sl"], "sl")
        
        # Skip if max positions (simple version: 1 main + 1 hedge max)
        if len(bt.positions) >= 2:
            continue
        
        # No positions - open main
        if not bt.positions:
            # Simple: alternate buy/sell or use trend
            side = "long" if trade_count % 2 == 0 else "short"
            sl_dist = stop_loss * 0.01
            
            if side == "long":
                entry = ask
                sl = entry - sl_dist
            else:
                entry = bid
                sl = entry + sl_dist
            
            bt.open_position(side, entry, lots, sl)
            trade_count += 1
        
        # One position - check for trailing
        elif len(bt.positions) == 1:
            pos = bt.positions[0]
            
            if pos["side"] == "long":
                profit_pts = (bid - pos["entry"]) / 0.01
                
                # Break even
                if profit_pts >= 50:  # 50 pips
                    be_sl = pos["entry"] + 10 * 0.01
                    if be_sl > pos["sl"]:
                        pos["sl"] = be_sl
                
                # Trailing
                elif profit_pts > 100:  # 100 pips
                    new_sl = bid - trailing * 0.01
                    if new_sl > pos["sl"]:
                        pos["sl"] = new_sl
            
            else:  # short
                profit_pts = (pos["entry"] - ask) / 0.01
                
                if profit_pts >= 50:
                    be_sl = pos["entry"] - 10 * 0.01
                    if be_sl < pos["sl"]:
                        pos["sl"] = be_sl
                
                elif profit_pts > 100:
                    new_sl = ask + trailing * 0.01
                    if new_sl < pos["sl"]:
                        pos["sl"] = new_sl
        
        # Progress report every 50k candles
        if i - last_report >= 50000:
            progress = (i / len(df)) * 100
            print(f"   Progress: {progress:.1f}% | Trades: {trade_count} | Balance: ${bt.balance:,.2f}")
            last_report = i
    
    # Close all positions
    bt.close_all(df.iloc[-1]["close"])
    
    # Results
    print("\n" + "=" * 60)
    print("📊 BACKTEST RESULTS")
    print("=" * 60)
    
    final_balance = bt.balance
    pnl = final_balance - balance
    pnl_pct = (pnl / balance) * 100
    
    print(f"\nInitial Balance: ${balance:,.2f}")
    print(f"Final Balance:   ${final_balance:,.2f}")
    print(f"P&L:             ${pnl:,.2f} ({pnl_pct:+.2f}%)")
    print(f"Total Trades:    {len(bt.trades)}")
    
    if bt.trades:
        wins = [t for t in bt.trades if t["profit"] > 0]
        losses = [t for t in bt.trades if t["profit"] <= 0]
        win_rate = len(wins) / len(bt.trades) * 100
        
        total_profit = sum(t["profit"] for t in wins)
        total_loss = sum(abs(t["profit"]) for t in losses)
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        print(f"Win Rate:        {win_rate:.1f}% ({len(wins)}/{len(bt.trades)})")
        print(f"Profit Factor:   {profit_factor:.2f}")
        print(f"Avg Win:         ${total_profit / len(wins) if wins else 0:,.2f}")
        print(f"Avg Loss:        ${total_loss / len(losses) if losses else 0:,.2f}")
    
    return {
        "balance": final_balance,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "trades": len(bt.trades),
    }


def optimize_parameters(data_file: str = "data/xauusd_1y_1m.csv"):
    """Grid search for best parameters"""
    print("🔍 PARAMETER OPTIMIZATION")
    print("=" * 60)
    
    best_result = None
    best_pnl = -float('inf')
    best_params = None
    
    # Parameter grid
    sl_values = [500, 800, 1000, 1500]
    trail_values = [100, 200, 400]
    
    results = []
    
    for sl in sl_values:
        for trail in trail_values:
            print(f"\n🧪 Testing SL={sl}, Trail={trail}")
            
            result = run_real_backtest(
                data_file=data_file,
                stop_loss=sl,
                trailing=trail,
                balance=10000,
                lots=0.02
            )
            
            results.append({
                "sl": sl,
                "trail": trail,
                **result
            })
            
            if result["pnl"] > best_pnl:
                best_pnl = result["pnl"]
                best_result = result
                best_params = (sl, trail)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📋 OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"{'SL':>6} | {'Trail':>6} | {'Trades':>8} | {'P&L':>12} | {'Return %':>10}")
    print("-" * 55)
    for r in results:
        print(f"{r['sl']:>6} | {r['trail']:>6} | {r['trades']:>8} | ${r['pnl']:>10,.2f} | {r['pnl_pct']:>9.2f}%")
    
    if best_params:
        print(f"\n🏆 Best Parameters:")
        print(f"   SL: {best_params[0]}")
        print(f"   Trail: {best_params[1]}")
        print(f"   P&L: ${best_pnl:,.2f}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh data")
    parser.add_argument("--optimize", action="store_true", help="Run optimization")
    parser.add_argument("--data", default="data/xauusd_1y_1m.csv")
    parser.add_argument("--sl", type=int, default=800)
    parser.add_argument("--trail", type=int, default=200)
    
    args = parser.parse_args()
    
    if args.optimize:
        optimize_parameters(args.data)
    else:
        run_real_backtest(
            data_file=args.data,
            stop_loss=args.sl,
            trailing=args.trail,
            fetch=args.fetch
        )
