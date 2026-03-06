"""
Fetch Historical Data from Exness Web API
Get real XAU/USD candle data directly from Exness (same as live trading)
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time
import argparse
from typing import List, Dict, Optional


class ExnessHistoryFetcher:
    """
    Fetch historical candle data from Exness Web API
    
    Based on traced endpoint:
    GET /v2/accounts/{id}/instruments/{symbol}/candles
    
    Query params:
    - time_frame: 1, 5, 15, 30, 60, 240, 1440 (minutes)
    - from: timestamp in milliseconds (starting point)
    - count: number of candles (-N = backwards from 'from')
    - price: bid or ask
    """
    
    TIMEFRAMES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }
    
    def __init__(
        self,
        account_id: int,
        token: str,
        server: str = "trial6",
        base_url: str = "https://rtapi-sg.eccweb.mobi/rtapi/mt5"
    ):
        self.account_id = account_id
        self.token = token
        self.server = server
        self.base_url = base_url
        self.session = requests.Session()
        self._update_headers()
        
    def _update_headers(self):
        """Set authentication headers"""
        self.session.headers.update({
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {self.token}",
            "content-type": "application/json",
            "referer": "https://my.exness.com/",
            "x-cid": "exterm_web_history_fetcher",
        })
    
    def _get_candles_url(self, symbol: str) -> str:
        """Get candles endpoint URL"""
        return f"{self.base_url}/{self.server}/v2/accounts/{self.account_id}/instruments/{symbol}/candles"
    
    def fetch_candles(
        self,
        symbol: str = "XAUUSDm",
        timeframe: str = "1m",
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        count: int = 1000,
        price_type: str = "bid"
    ) -> List[Dict]:
        """
        Fetch candles from Exness API
        
        Args:
            symbol: Trading pair (XAUUSDm, BTCUSDm, etc)
            timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d
            from_time: Start datetime (default: now - count candles)
            to_time: End datetime (optional)
            count: Number of candles to fetch (max ~1000 per request)
            price_type: bid or ask
        
        Returns:
            List of candles with timestamp, open, high, low, close, volume
        """
        tf_value = self.TIMEFRAMES.get(timeframe, 1)
        
        # Calculate 'from' timestamp
        if from_time is None:
            # Default: fetch backwards from now
            from_ts = int(time.time() * 1000) + 86400000  # Tomorrow (future)
        else:
            from_ts = int(from_time.timestamp() * 1000)
        
        url = self._get_candles_url(symbol)
        params = {
            "time_frame": tf_value,
            "from": from_ts,
            "count": -count,  # Negative = backwards
            "price": price_type
        }
        
        print(f"📡 Fetching {count} {timeframe} candles for {symbol}...")
        print(f"   From: {datetime.fromtimestamp(from_ts/1000)}")
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            candles = data.get("price_history", [])
            
            # Convert to standard format
            result = []
            for c in candles:
                result.append({
                    "timestamp": c["t"],
                    "datetime": datetime.fromtimestamp(c["t"] / 1000),
                    "open": c["o"],
                    "high": c["h"],
                    "low": c["l"],
                    "close": c["c"],
                    "volume": c["v"]
                })
            
            print(f"✅ Fetched {len(result)} candles")
            if result:
                print(f"   Range: {result[0]['datetime']} to {result[-1]['datetime']}")
                print(f"   Price: ${result[0]['low']:.2f} - ${result[-1]['high']:.2f}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error fetching candles: {e}")
            if hasattr(e, 'response'):
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:200]}")
            return []
    
    def fetch_range(
        self,
        symbol: str = "XAUUSDm",
        timeframe: str = "1m",
        start_date: datetime = None,
        end_date: datetime = None,
        batch_size: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch candles for a date range (handles pagination)
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            start_date: Start datetime
            end_date: End datetime (default: now)
            batch_size: Candles per request (max 1000)
        
        Returns:
            DataFrame with OHLCV data
        """
        if end_date is None:
            end_date = datetime.now()
        
        if start_date is None:
            # Default: 1 month ago
            start_date = end_date - timedelta(days=30)
        
        print(f"📊 Fetching {symbol} {timeframe} data")
        print(f"   From: {start_date}")
        print(f"   To: {end_date}")
        print()
        
        all_candles = []
        current_end = end_date
        
        while current_end > start_date:
            candles = self.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                from_time=current_end,
                count=batch_size
            )
            
            if not candles:
                break
            
            all_candles.extend(candles)
            
            # Update current_end to fetch older candles
            earliest_ts = min(c["timestamp"] for c in candles)
            current_end = datetime.fromtimestamp(earliest_ts / 1000)
            
            # Stop if we've reached start_date
            if current_end <= start_date:
                break
            
            # Rate limit protection
            time.sleep(0.5)
        
        # Filter to requested range
        start_ts = start_date.timestamp() * 1000
        end_ts = end_date.timestamp() * 1000
        
        filtered = [
            c for c in all_candles
            if start_ts <= c["timestamp"] <= end_ts
        ]
        
        # Remove duplicates and sort
        seen_ts = set()
        unique = []
        for c in sorted(filtered, key=lambda x: x["timestamp"]):
            if c["timestamp"] not in seen_ts:
                seen_ts.add(c["timestamp"])
                unique.append(c)
        
        # Convert to DataFrame
        df = pd.DataFrame(unique)
        
        if not df.empty:
            df = df.sort_values("timestamp").reset_index(drop=True)
            print(f"\n✅ Total: {len(df)} unique candles")
        
        return df
    
    def save_to_csv(self, df: pd.DataFrame, filepath: str):
        """Save DataFrame to CSV"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False)
        print(f"💾 Saved to: {filepath}")
    
    def convert_to_backtest_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert to format expected by backtest engine"""
        return pd.DataFrame({
            "timestamp": df["timestamp"],
            "open": df["open"],
            "high": df["high"],
            "low": df["low"],
            "close": df["close"],
            "volume": df["volume"]
        })


def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical data from Exness Web API"
    )
    parser.add_argument(
        "--account",
        type=int,
        default=int(os.getenv("EXNESS_ACCOUNT_ID", "413461571")),
        help="Exness account ID"
    )
    parser.add_argument(
        "--token",
        default=os.getenv("EXNESS_TOKEN"),
        help="Exness JWT token (or set EXNESS_TOKEN env)"
    )
    parser.add_argument(
        "--server",
        default="trial6",
        help="Server (trial6, trial5, real17, etc)"
    )
    parser.add_argument(
        "--symbol",
        default="XAUUSDm",
        help="Symbol to fetch (XAUUSDm, BTCUSDm, etc)"
    )
    parser.add_argument(
        "--timeframe",
        default="1m",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        help="Candle timeframe"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to fetch"
    )
    parser.add_argument(
        "--output",
        default="data/exness_xauusd.csv",
        help="Output CSV file"
    )
    parser.add_argument(
        "--format",
        choices=["standard", "backtest"],
        default="standard",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    if not args.token:
        print("❌ Please provide --token or set EXNESS_TOKEN environment variable")
        print("   Get token from browser DevTools (see docs)")
        return
    
    # Create fetcher
    fetcher = ExnessHistoryFetcher(
        account_id=args.account,
        token=args.token,
        server=args.server
    )
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    # Fetch data
    df = fetcher.fetch_range(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if df.empty:
        print("❌ No data fetched")
        return
    
    # Convert format if needed
    if args.format == "backtest":
        df = fetcher.convert_to_backtest_format(df)
    
    # Save
    fetcher.save_to_csv(df, args.output)
    
    # Show sample
    print("\n📋 Sample data:")
    print(df.head(10))
    
    print("\n📊 Statistics:")
    print(f"Total candles: {len(df)}")
    print(f"Period: {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]) / 1000 / 3600:.1f} hours")
    print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
    print(f"Avg volume: {df['volume'].mean():.0f}")


if __name__ == "__main__":
    import os
    main()
