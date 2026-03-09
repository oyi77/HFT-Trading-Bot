#!/usr/bin/env python3
"""
Fetch 3 years of historical data from Exness for multiple timeframes.
Usage: python tools/fetch_3year_data.py --token "YOUR_JWT_TOKEN" --account 413461571
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time
import argparse
import os
from typing import List, Dict, Optional


class ExnessHistoryFetcher:
    """Fetch historical candle data from Exness Web API"""

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
        base_url: str = "https://rtapi-sg.eccweb.mobi/rtapi/mt5",
    ):
        self.account_id = account_id
        self.token = token
        self.server = server
        self.base_url = base_url
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self):
        """Set authentication headers"""
        self.session.headers.update(
            {
                "accept": "application/json, text/plain, */*",
                "authorization": f"Bearer {self.token}",
                "content-type": "application/json",
                "referer": "https://my.exness.com/",
                "x-cid": "exterm_web_history_fetcher",
            }
        )

    def _get_candles_url(self, symbol: str) -> str:
        """Get candles endpoint URL"""
        return f"{self.base_url}/{self.server}/v2/accounts/{self.account_id}/instruments/{symbol}/candles"

    def fetch_candles(
        self,
        symbol: str = "XAUUSDm",
        timeframe: str = "1h",
        from_time: Optional[datetime] = None,
        count: int = 1000,
        price_type: str = "bid",
    ) -> List[Dict]:
        """Fetch candles from Exness API"""
        tf_value = self.TIMEFRAMES.get(timeframe, 60)

        if from_time is None:
            from_ts = int(time.time() * 1000) + 86400000
        else:
            from_ts = int(from_time.timestamp() * 1000)

        url = self._get_candles_url(symbol)
        params = {
            "time_frame": tf_value,
            "from": from_ts,
            "count": -count,
            "price": price_type,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            candles = data.get("price_history", [])

            result = []
            for c in candles:
                result.append(
                    {
                        "timestamp": c["t"],
                        "datetime": datetime.fromtimestamp(c["t"] / 1000),
                        "open": c["o"],
                        "high": c["h"],
                        "low": c["l"],
                        "close": c["c"],
                        "volume": c["v"],
                    }
                )

            return result

        except Exception as e:
            print(f"❌ Error: {e}")
            if hasattr(e, "response"):
                print(f"   Status: {e.response.status_code}")
            return []

    def fetch_range(
        self,
        symbol: str = "XAUUSDm",
        timeframe: str = "1h",
        start_date: datetime = None,
        end_date: datetime = None,
        batch_size: int = 1000,
        rate_limit: float = 0.3,
    ) -> pd.DataFrame:
        """Fetch candles for a date range with pagination"""
        if end_date is None:
            end_date = datetime.now()

        if start_date is None:
            start_date = end_date - timedelta(days=365)

        print(f"📊 {symbol} {timeframe}: {start_date.date()} to {end_date.date()}")

        all_candles = []
        current_end = end_date
        request_count = 0

        while current_end > start_date:
            candles = self.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                from_time=current_end,
                count=batch_size,
            )

            if not candles:
                break

            all_candles.extend(candles)
            request_count += 1

            earliest_ts = min(c["timestamp"] for c in candles)
            current_end = datetime.fromtimestamp(earliest_ts / 1000)

            if current_end <= start_date:
                break

            time.sleep(rate_limit)

        if not all_candles:
            print(f"   ⚠️ No data fetched")
            return pd.DataFrame()

        # Filter to requested range
        start_ts = start_date.timestamp() * 1000
        end_ts = end_date.timestamp() * 1000

        filtered = [c for c in all_candles if start_ts <= c["timestamp"] <= end_ts]

        # Remove duplicates
        seen_ts = set()
        unique = []
        for c in sorted(filtered, key=lambda x: x["timestamp"]):
            if c["timestamp"] not in seen_ts:
                seen_ts.add(c["timestamp"])
                unique.append(c)

        df = pd.DataFrame(unique)

        if not df.empty:
            df = df.sort_values("timestamp").reset_index(drop=True)
            print(f"   ✅ {len(df)} candles ({request_count} requests)")

        return df

    def save_to_csv(self, df: pd.DataFrame, filepath: str):
        """Save DataFrame to CSV"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False)
        print(f"   💾 Saved: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Fetch 3 years of historical data")
    parser.add_argument("--token", required=True, help="Exness JWT token")
    parser.add_argument("--account", type=int, default=413461571, help="Account ID")
    parser.add_argument("--server", default="trial6", help="Server")
    parser.add_argument("--symbol", default="XAUUSDm", help="Trading symbol")
    # Timeframes to fetch
    parser.add_argument(
        "--timeframes",
        default="1h,4h,1d",
        help="Comma-separated timeframes (default: 1h,4h,1d)",
    )
    # Years of data
    parser.add_argument("--years", type=int, default=3, help="Years of data to fetch")
    # Output directory
    parser.add_argument("--output", default="data/historical", help="Output directory")
    # Rate limit (seconds between requests)
    parser.add_argument(
        "--rate-limit", type=float, default=0.3, help="Rate limit (seconds)"
    )

    args = parser.parse_args()

    # Parse timeframes
    timeframes = [tf.strip() for tf in args.timeframes.split(",")]

    print("=" * 60)
    print("📈 EXNESS 3-YEAR HISTORICAL DATA FETCHER")
    print("=" * 60)
    print(f"Account: {args.account}")
    print(f"Symbol:  {args.symbol}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Years:   {args.years}")
    print(f"Output:  {args.output}")
    print("=" * 60)
    print()

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.years * 365)

    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")
    print()

    # Create fetcher
    fetcher = ExnessHistoryFetcher(
        account_id=args.account, token=args.token, server=args.server
    )

    # Fetch each timeframe
    results = {}
    for tf in timeframes:
        print(f"\n{'=' * 60}")
        print(f"🔄 Fetching {tf} timeframe...")
        print(f"{'=' * 60}")

        df = fetcher.fetch_range(
            symbol=args.symbol,
            timeframe=tf,
            start_date=start_date,
            end_date=end_date,
            rate_limit=args.rate_limit,
        )

        if not df.empty:
            # Save to CSV
            filename = f"{args.symbol}_{tf}_{args.years}y.csv"
            filepath = Path(args.output) / filename
            fetcher.save_to_csv(df, str(filepath))

            results[tf] = df

            # Print stats
            print(f"\n📊 Statistics for {tf}:")
            print(f"   Total candles: {len(df)}")
            print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            print(f"   Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
            print(f"   Avg volume: {df['volume'].mean():.0f}")
        else:
            print(f"   ❌ No data fetched for {tf}")

        # Small delay between timeframes
        time.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    for tf, df in results.items():
        print(
            f"  {tf:4s}: {len(df):>8,} candles | {df['datetime'].min().date()} to {df['datetime'].max().date()}"
        )

    print("\n✅ All data fetched successfully!")
    print(f"📁 Files saved to: {args.output}/")


if __name__ == "__main__":
    main()
