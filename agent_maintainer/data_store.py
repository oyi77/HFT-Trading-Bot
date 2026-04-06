"""
DataStore — single source of truth untuk semua data OHLCV.

Priority:
1. Local historical CSV (data/historical/) — 3 tahun, high quality
2. SQLite cache (data/market_data.db)
3. Fallback: yfinance (Yahoo Finance)

Usage:
    from agent_maintainer.data_store import DataStore
    ds = DataStore()
    m15 = ds.get("M15", days=30)   # returns DataFrame ready for backtest
    h1  = ds.get("H1",  days=60)
"""
import os, sys, sqlite3, warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

REPO_ROOT    = Path(__file__).parent.parent
DATA_DIR     = REPO_ROOT / "data"
HIST_DIR     = DATA_DIR / "historical"
DB_PATH      = DATA_DIR / "market_data.db"

# Local CSV mapping: timeframe → filename pattern
LOCAL_FILES = {
    "M5":  ["XAUUSDm_5m_2y.csv", "XAUUSDm_5m_1y.csv"],
    "M15": ["XAUUSDm_15m_3y.csv"],
    "M30": ["XAUUSDm_30m_3y.csv"],
    "H1":  ["XAUUSDm_1h_3y.csv"],
    "H4":  ["XAUUSDm_4h_3y.csv"],
    "D1":  ["XAUUSDm_1d_3y.csv"],
}

# yfinance interval mapping
YF_INTERVALS = {
    "M1":  "1m",
    "M5":  "5m",
    "M15": "15m",
    "M30": "30m",
    "H1":  "1h",
    "H4":  "1h",   # yfinance has no 4h; aggregate manually
    "D1":  "1d",
}

# yfinance max period per interval
YF_PERIODS = {
    "M1":  "7d",
    "M5":  "60d",
    "M15": "60d",
    "M30": "60d",
    "H1":  "730d",
    "D1":  "max",
}


class DataStore:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self._init_db()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get(self, timeframe: str = "M15", days: int = 30) -> pd.DataFrame:
        """
        Get OHLCV data for given timeframe and lookback window.
        Returns DataFrame with columns: timestamp(int), open, high, low, close
        Ready for BacktestEngine.
        """
        tf = timeframe.upper()

        # 1. Try local CSV — auto-update if stale
        df_local = self._load_local(tf)
        if df_local is not None and len(df_local) > 0:
            last_ts = df_local["timestamp"].max()
            age_days = (datetime.now(timezone.utc).timestamp() - last_ts) / 86400
            if age_days > 1.0:
                print(f"[DataStore] {tf} local data is {age_days:.1f}d old — updating…")
                df_new = self._fetch_yfinance(tf, days=min(int(age_days) + 5, 60))
                if df_new is not None and len(df_new) > 0:
                    df_local = self._append_local(tf, df_local, df_new)

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_ts = int(cutoff.timestamp())
            df_filtered = df_local[df_local["timestamp"] >= cutoff_ts].copy()
            if len(df_filtered) > 50:
                print(f"[DataStore] {tf} from local CSV: {len(df_filtered)} bars ({days}d)")
                return df_filtered

        # 2. Try SQLite cache
        df = self._load_cache(tf, days)
        if df is not None and len(df) > 50:
            print(f"[DataStore] {tf} from SQLite cache: {len(df)} bars ({days}d)")
            return df

        # 3. Fallback: yfinance
        print(f"[DataStore] {tf} — fetching from yfinance (fallback)…")
        df = self._fetch_yfinance(tf, days)
        if df is not None and len(df) > 0:
            self._save_cache(tf, df)
            return df

        raise RuntimeError(f"[DataStore] No data available for {tf}")

    def latest_price(self) -> float:
        """Get latest XAU/USD price."""
        try:
            import yfinance as yf
            t = yf.download("GC=F", period="1d", interval="5m", progress=False)
            if hasattr(t.columns, "droplevel") and t.columns.nlevels > 1:
                t.columns = t.columns.droplevel(1)
            return float(t["Close"].iloc[-1])
        except Exception:
            return 0.0

    def save_forward_result(self, preset: str, timeframe: str, result: dict):
        """Persist forward-test result for historical tracking."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO forward_results
            (ts, preset, timeframe, return_pct, trades, win_rate, profit_factor, sharpe, max_dd, net_profit, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(datetime.now(timezone.utc).timestamp()),
            preset, timeframe,
            result.get("return_pct", 0),
            result.get("trades", 0),
            result.get("win_rate", 0),
            result.get("profit_factor", 0),
            result.get("sharpe", 0),
            result.get("max_dd", 0),
            result.get("net_profit", 0),
            result.get("status", "OK"),
        ))
        conn.commit()
        conn.close()

    def get_history(self, preset: str = None, days: int = 30) -> pd.DataFrame:
        """Get historical forward-test results."""
        conn = sqlite3.connect(DB_PATH)
        cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        if preset:
            df = pd.read_sql("SELECT * FROM forward_results WHERE preset=? AND ts>=? ORDER BY ts",
                             conn, params=(preset, cutoff))
        else:
            df = pd.read_sql("SELECT * FROM forward_results WHERE ts>=? ORDER BY ts",
                             conn, params=(cutoff,))
        conn.close()
        df["date"] = pd.to_datetime(df["ts"], unit="s").dt.strftime("%Y-%m-%d")
        return df

    def summary(self):
        """Print summary of what data is available."""
        print(f"\n{'='*60}")
        print(f"DataStore Summary")
        print(f"{'='*60}")
        print(f"Local CSVs:")
        for tf, files in LOCAL_FILES.items():
            for fname in files:
                fpath = HIST_DIR / fname
                if fpath.exists():
                    df = self._load_local(tf)
                    if df is not None:
                        ts_min = pd.to_datetime(df["timestamp"].min(), unit="s").strftime("%Y-%m-%d")
                        ts_max = pd.to_datetime(df["timestamp"].max(), unit="s").strftime("%Y-%m-%d")
                        print(f"  {tf:>4}: {fname:<35} {len(df):>7} bars | {ts_min} → {ts_max}")
        print(f"\nSQLite DB: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        n = conn.execute("SELECT COUNT(*) FROM forward_results").fetchone()[0]
        conn.close()
        print(f"  Forward results stored: {n}")
        print(f"{'='*60}\n")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol    TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                ts        INTEGER NOT NULL,
                open      REAL, high REAL, low REAL, close REAL, volume REAL,
                UNIQUE(symbol, timeframe, ts)
            );
            CREATE INDEX IF NOT EXISTS idx_ohlcv ON ohlcv_cache(symbol, timeframe, ts);

            CREATE TABLE IF NOT EXISTS forward_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            INTEGER NOT NULL,
                preset        TEXT NOT NULL,
                timeframe     TEXT NOT NULL,
                return_pct    REAL,
                trades        INTEGER,
                win_rate      REAL,
                profit_factor REAL,
                sharpe        REAL,
                max_dd        REAL,
                net_profit    REAL,
                status        TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_fwd ON forward_results(preset, ts);
        """)
        conn.commit()
        conn.close()

    def _append_local(self, timeframe: str, existing: pd.DataFrame, new_data: pd.DataFrame) -> pd.DataFrame:
        """Append new_data to existing, dedup, save back to CSV."""
        try:
            # Normalize new_data columns
            new_data = new_data.copy()
            new_data.columns = [c.lower() for c in new_data.columns]
            for col in ["open", "high", "low", "close", "timestamp"]:
                if col not in new_data.columns:
                    return existing

            combined = pd.concat([existing, new_data[["timestamp","open","high","low","close"]]])
            combined = combined.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

            # Save back to first matching file
            files = LOCAL_FILES.get(timeframe, [])
            if files:
                fpath = HIST_DIR / files[0]
                if fpath.exists():
                    combined.to_csv(fpath, index=False)
                    print(f"[DataStore] Updated {fpath.name}: {len(combined)} bars total")
            return combined
        except Exception as e:
            print(f"[DataStore] append error: {e}")
            return existing

    def _load_local(self, timeframe: str) -> pd.DataFrame | None:
        files = LOCAL_FILES.get(timeframe, [])
        for fname in files:
            fpath = HIST_DIR / fname
            if fpath.exists():
                df = pd.read_csv(fpath)
                df.columns = [c.lower() for c in df.columns]
                # Ensure timestamp column exists as int
                if "timestamp" not in df.columns:
                    # Try parsing datetime column
                    dt_col = next((c for c in df.columns if "time" in c or "date" in c), None)
                    if dt_col:
                        df["timestamp"] = pd.to_datetime(df[dt_col]).view("int64") // 10**9
                    else:
                        continue
                ts_vals = df["timestamp"].astype(int)
                # Auto-detect ms vs seconds: ms timestamps are ~1e12, seconds ~1e9
                if ts_vals.median() > 1e11:
                    ts_vals = ts_vals // 1000
                df["timestamp"] = ts_vals
                # Ensure required columns
                for col in ["open", "high", "low", "close"]:
                    if col not in df.columns:
                        return None
                return df.sort_values("timestamp").reset_index(drop=True)
        return None

    def _load_cache(self, timeframe: str, days: int) -> pd.DataFrame | None:
        try:
            conn = sqlite3.connect(DB_PATH)
            cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
            df = pd.read_sql(
                "SELECT ts as timestamp, open, high, low, close FROM ohlcv_cache "
                "WHERE symbol='XAUUSD' AND timeframe=? AND ts>=? ORDER BY ts",
                conn, params=(timeframe, cutoff)
            )
            conn.close()
            return df if len(df) > 0 else None
        except Exception:
            return None

    def _save_cache(self, timeframe: str, df: pd.DataFrame):
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = []
            for _, row in df.iterrows():
                rows.append((
                    "XAUUSD", timeframe, int(row["timestamp"]),
                    float(row.get("open", row.get("Open", 0))),
                    float(row.get("high", row.get("High", 0))),
                    float(row.get("low",  row.get("Low",  0))),
                    float(row.get("close", row.get("Close", 0))),
                    0.0,
                ))
            conn.executemany(
                "INSERT OR IGNORE INTO ohlcv_cache (symbol,timeframe,ts,open,high,low,close,volume) "
                "VALUES (?,?,?,?,?,?,?,?)", rows
            )
            conn.commit()
            conn.close()
            print(f"[DataStore] Cached {len(rows)} bars ({timeframe}) to SQLite")
        except Exception as e:
            print(f"[DataStore] Cache write error: {e}")

    def _fetch_yfinance(self, timeframe: str, days: int) -> pd.DataFrame | None:
        try:
            import yfinance as yf
            interval = YF_INTERVALS.get(timeframe, "15m")
            # cap days to yfinance limits
            max_days = {"M1": 7, "M5": 60, "M15": 60, "M30": 60, "H1": 730}.get(timeframe, 730)
            actual_days = min(days, max_days)
            period = f"{actual_days}d"

            df = yf.download("GC=F", period=period, interval=interval, progress=False)
            if hasattr(df.columns, "droplevel") and df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(1)
            df = df.copy()
            df.columns = [c.lower() for c in df.columns]
            df["timestamp"] = df.index.view("int64") // 10**9
            df = df.reset_index(drop=True)
            return df
        except Exception as e:
            print(f"[DataStore] yfinance error: {e}")
            return None


if __name__ == "__main__":
    ds = DataStore()
    ds.summary()
    m15 = ds.get("M15", days=30)
    print(f"M15 sample (last 3): \n{m15[['timestamp','open','high','low','close']].tail(3)}")
    h1 = ds.get("H1", days=60)
    print(f"H1 sample (last 3): \n{h1[['timestamp','open','high','low','close']].tail(3)}")
