"""
Fetch real XAU/USD data from Yahoo Finance for backtesting.
Uses yfinance to download historical gold data.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import argparse


def fetch_xau_data(
    period: str = "1y",
    interval: str = "1m",
    output_file: str = None
) -> pd.DataFrame:
    """
    Fetch XAU/USD data from Yahoo Finance
    
    Args:
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        output_file: Output CSV file path
    
    Returns:
        DataFrame with OHLCV data
    """
    # XAU/USD ticker on Yahoo Finance
    # GC=F is Gold Futures (most liquid)
    ticker = "GC=F"
    
    print(f"📊 Fetching XAU/USD ({ticker}) data...")
    print(f"   Period: {period}, Interval: {interval}")
    
    # Download data
    gold = yf.Ticker(ticker)
    df = gold.history(period=period, interval=interval)
    
    if df.empty:
        print("❌ No data downloaded!")
        return df
    
    # Reset index to make datetime a column
    df.reset_index(inplace=True)
    
    # Rename columns to match our format
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    
    # Convert datetime to timestamp (milliseconds)
    if "datetime" in df.columns:
        df["timestamp"] = df["datetime"].astype(int) // 10**6
    elif "date" in df.columns:
        df["timestamp"] = df["date"].astype(int) // 10**6
    
    print(f"✅ Downloaded {len(df)} candles")
    print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"   Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
    
    # Save to CSV
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False)
        print(f"💾 Saved to: {output_file}")
    
    return df


def convert_to_exness_format(
    df: pd.DataFrame,
    output_file: str = None
) -> pd.DataFrame:
    """
    Convert Yahoo Finance format to Exness-like format for backtesting
    """
    # Create OHLCV format matching Exness API response
    result = pd.DataFrame({
        "timestamp": df["timestamp"],
        "o": df["open"],
        "h": df["high"],
        "l": df["low"],
        "c": df["close"],
        "v": df["volume"].astype(int)
    })
    
    if output_file:
        result.to_csv(output_file, index=False)
        print(f"💾 Converted to Exness format: {output_file}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch XAU/USD data for backtesting")
    parser.add_argument("--period", default="1y", help="Data period (1y, 6mo, etc)")
    parser.add_argument("--interval", default="1m", help="Data interval (1m, 5m, 1h, 1d)")
    parser.add_argument("--output", default="data/xauusd_yfinance.csv", help="Output file")
    parser.add_argument("--exness-format", action="store_true", help="Convert to Exness format")
    
    args = parser.parse_args()
    
    # Fetch data
    df = fetch_xau_data(args.period, args.interval, args.output)
    
    if args.exness_format:
        exness_file = args.output.replace(".csv", "_exness.csv")
        convert_to_exness_format(df, exness_file)
    
    # Show sample
    print("\n📋 Sample data:")
    print(df.head(10))
    
    print("\n📊 Statistics:")
    print(f"Total candles: {len(df)}")
    print(f"Avg daily range: ${(df['high'] - df['low']).mean():.2f}")
    print(f"Volatility (std): ${df['close'].std():.2f}")


if __name__ == "__main__":
    main()
