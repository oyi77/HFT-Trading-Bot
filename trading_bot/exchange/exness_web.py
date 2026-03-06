"""
Exness Web Trading API Provider
Direct integration dengan Exness Web Terminal API berdasarkan traced data.
"""

import requests
import time
import functools
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from trading_bot.core.models import Position, Order
from trading_bot.core.interfaces import Exchange


def retry_with_backoff(max_retries=3, backoff_factor=1.0, retry_codes=(429, 503, 502)):
    """
    Decorator for retrying API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Base delay between retries (will be multiplied by 2^attempt)
        retry_codes: HTTP status codes that trigger a retry
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    if hasattr(e.response, "status_code"):
                        status_code = e.response.status_code
                        if status_code in retry_codes:
                            sleep_time = backoff_factor * (2**attempt)
                            print(
                                f"⚠️ Rate limited (HTTP {status_code}). Retrying in {sleep_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            time.sleep(sleep_time)
                            continue
                    raise
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        sleep_time = backoff_factor * (2**attempt)
                        print(
                            f"⚠️ Request failed: {e}. Retrying in {sleep_time}s... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(sleep_time)
                        continue
                    raise
            # If we've exhausted all retries, raise the last exception
            if last_exception:
                raise last_exception
            return None

        return wrapper

    return decorator


@dataclass
class ExnessConfig:
    """Configuration for Exness Web API"""

    account_id: int
    token: str  # JWT Bearer token
    server: str = "trial6"  # mt5 trial6, trial5, real17, etc
    base_url: str = "https://rtapi-sg.eccweb.mobi/rtapi/mt5"


class ExnessWebProvider(Exchange):
    """
    Exness Web Trading API Provider.

    Based on reverse-engineered API from Exness Web Terminal.
    Supports: orders, positions, balance, candles
    """

    # Timeframe mapping
    TIMEFRAMES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }

    # Order types
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5

    def __init__(self, config: ExnessConfig):
        self.config = config
        self.session = requests.Session()
        self._update_headers()

        # Request caching to reduce API calls
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = {
            "balance": 1.0,  # 1 second for balance
            "equity": 1.0,  # 1 second for equity
            "positions": 0.5,  # 0.5 seconds for positions
            "price": 0.5,  # 0.5 seconds for price
            "account_info": 5.0,  # 5 seconds for account info
            "margin": 1.0,  # 1 second for margin
        }

        # Rate limiting tracking
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # Minimum 100ms between requests
        self._requests_in_last_second = 0
        self._last_second_reset = time.time()
        self._max_requests_per_second = 10  # Max 10 requests per second

    def _update_headers(self):
        """Set authentication headers"""
        self.session.headers.update(
            {
                "accept": "application/json, text/plain, */*",
                "authorization": f"Bearer {self.config.token}",
                "content-type": "application/json",
                "referer": "https://my.exness.com/",
                "x-cid": "exterm_web_python_bot",
            }
        )

    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()

        # Reset counter every second
        if current_time - self._last_second_reset >= 1.0:
            self._requests_in_last_second = 0
            self._last_second_reset = current_time

        # Check if we're exceeding max requests per second
        if self._requests_in_last_second >= self._max_requests_per_second:
            sleep_time = 1.0 - (current_time - self._last_second_reset)
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._requests_in_last_second = 0
            self._last_second_reset = time.time()

        # Enforce minimum interval between requests
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)

        self._last_request_time = time.time()
        self._requests_in_last_second += 1

    def _get_cached(self, cache_key: str) -> Any:
        """Get value from cache if still valid."""
        if cache_key not in self._cache:
            return None

        ttl = self._cache_ttl.get(cache_key, 1.0)
        if time.time() - self._cache_timestamps.get(cache_key, 0) > ttl:
            return None

        return self._cache[cache_key]

    def _set_cached(self, cache_key: str, value: Any):
        """Store value in cache with timestamp."""
        self._cache[cache_key] = value
        self._cache_timestamps[cache_key] = time.time()

    def _get_base_url(self) -> str:
        """Get base URL for account"""
        return f"{self.config.base_url}/{self.config.server}/v1/accounts/{self.config.account_id}"

    def _get_v2_url(self) -> str:
        """Get v2 base URL for candles"""
        return f"{self.config.base_url}/{self.config.server}/v2/accounts/{self.config.account_id}"

    # ==================== Exchange Interface ====================

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def connect(self) -> bool:
        """Test connection by fetching account info"""
        try:
            self._enforce_rate_limit()
            response = self.session.get(f"{self._get_base_url()}/server")
            response.raise_for_status()
            data = response.json()
            print(f"✅ Connected to Exness {data['server']['name']}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_balance(self) -> float:
        """Get account balance with caching"""
        cached = self._get_cached("balance")
        if cached is not None:
            return cached

        try:
            self._enforce_rate_limit()
            response = self.session.get(f"{self._get_base_url()}/balance")
            response.raise_for_status()
            data = response.json()
            balance = float(data.get("balance", 0))
            self._set_cached("balance", balance)
            return balance
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_equity(self) -> float:
        """Get account equity with caching"""
        cached = self._get_cached("equity")
        if cached is not None:
            return cached

        try:
            self._enforce_rate_limit()
            response = self.session.get(f"{self._get_base_url()}/balance")
            response.raise_for_status()
            data = response.json()
            equity = float(data.get("equity", 0))
            self._set_cached("equity", equity)
            return equity
        except Exception as e:
            print(f"Error getting equity: {e}")
            return 0.0

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions with caching"""
        cache_key = f"positions_{symbol or 'all'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            self._enforce_rate_limit()
            response = self.session.get(f"{self._get_base_url()}/positions")
            response.raise_for_status()
            data = response.json()

            positions = []
            for pos in data.get("positions", []):
                if symbol and pos["instrument"] != symbol:
                    continue

                positions.append(
                    Position(
                        id=str(pos["position_id"]),
                        symbol=pos["instrument"],
                        side="long" if pos["type"] == 0 else "short",
                        entry_price=float(pos["open_price"]),
                        amount=float(pos["volume"]),
                        unrealized_pnl=float(pos.get("profit", 0)),
                        sl=float(pos.get("sl", 0)) if pos.get("sl") else 0,
                        tp=float(pos.get("tp", 0)) if pos.get("tp") else 0,
                        open_time=pos.get("open_time", 0),
                    )
                )
            self._set_cached(cache_key, positions)
            return positions
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def open_position(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        price: Optional[float] = None,
    ) -> Optional[str]:
        """Open market order"""
        order_type = self.ORDER_TYPE_BUY if side == "long" else self.ORDER_TYPE_SELL

        # Get current price if not provided
        if price is None:
            price = self.get_price(symbol)

        return self._place_order(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
        )

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def close_position(self, position_id: str, symbol: Optional[str] = None) -> bool:
        """Close position by ID"""
        try:
            self._enforce_rate_limit()
            # Exness uses order to close position
            # Position ID is the ticket to close
            url = f"{self._get_base_url()}/positions/{position_id}"
            response = self.session.delete(url)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error closing position {position_id}: {e}")
            return False

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def modify_position(self, ticket: str, sl: float = None, tp: float = None) -> bool:
        """Modify position SL/TP (implements Exchange interface)"""
        try:
            self._enforce_rate_limit()
            url = f"{self._get_base_url()}/positions/{ticket}"
            payload = {}
            if sl is not None:
                payload["sl"] = sl
            if tp is not None:
                payload["tp"] = tp

            response = self.session.patch(url, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error modifying position {ticket}: {e}")
            return False

    # Alias for backward compatibility
    modify_position_sl = modify_position

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_price(self, symbol: str) -> float:
        """Get current price for symbol with caching"""
        cache_key = f"price_{symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            self._enforce_rate_limit()
            # Get latest candle as price reference
            candles = self.get_candles(symbol, timeframe="1m", limit=1)
            if candles:
                price = candles[-1]["close"]
                self._set_cached(cache_key, price)
                return price
            return 0.0
        except Exception as e:
            print(f"Error getting price: {e}")
            return 0.0

    # ==================== Extended Methods ====================

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def _place_order(
        self,
        symbol: str,
        order_type: int,
        volume: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        deviation: int = 0,
    ) -> Optional[str]:
        """Place order with Exness API"""
        try:
            self._enforce_rate_limit()
            url = f"{self._get_base_url()}/orders"

            order_data = {
                "instrument": symbol,
                "type": order_type,
                "volume": volume,
                "price": price,
                "deviation": deviation,
                "sl": sl if sl else 0,
                "tp": tp if tp else 0,
                "oneClick": False,
                "operationDuration": 0,
            }

            payload = {
                "order": order_data,
                "ga": "",
                "fp": "",
                "track_uid": "",
                "cid": "exterm_web_python_bot",
                "agent_timestamp": str(int(time.time() * 1000)),
                "agent": "python_bot",
                "agent_full_path": "",
            }

            response = self.session.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if "order" in data and "ticket_id" in data["order"]:
                return str(data["order"]["ticket_id"])
            return None

        except Exception as e:
            print(f"Error placing order: {e}")
            if hasattr(e, "response"):
                print(f"Response: {e.response.text}")
            return None

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 300,
        price_type: str = "bid",
        from_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get candlestick data with retry and rate limiting"""
        try:
            self._enforce_rate_limit()
            tf_value = self.TIMEFRAMES.get(timeframe, 1)

            # Use v2 API for candles
            url = f"{self._get_v2_url()}/instruments/{symbol}/candles"

            # If from_time not specified, use future timestamp to get latest
            if from_time is None:
                from_time = 9007199254740991  # Far future = get latest

            params = {
                "time_frame": tf_value,
                "from": from_time,
                "count": -limit,  # Negative = backwards
                "price": price_type,
            }

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            candles = []
            for c in data.get("price_history", []):
                candles.append(
                    {
                        "timestamp": c["t"],
                        "open": c["o"],
                        "high": c["h"],
                        "low": c["l"],
                        "close": c["c"],
                        "volume": c["v"],
                    }
                )
            return candles

        except Exception as e:
            print(f"Error getting candles: {e}")
            return []

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get historical candle data for a specific time range

        Args:
            symbol: Trading pair
            timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds (default: now)
            limit: Max candles per request

        Returns:
            List of candles sorted by timestamp (oldest first)
        """
        import time

        if end_time is None:
            end_time = int(time.time() * 1000)

        all_candles = []
        current_from = end_time

        while current_from > (start_time or 0):
            candles = self.get_candles(
                symbol=symbol, timeframe=timeframe, limit=limit, from_time=current_from
            )

            if not candles:
                break

            all_candles.extend(candles)

            # Get earliest timestamp from this batch
            earliest_ts = min(c["timestamp"] for c in candles)

            # If we've reached start_time, stop
            if start_time and earliest_ts <= start_time:
                break

            # Update current_from for next batch (go further back)
            current_from = earliest_ts - 1

            # Rate limit
            time.sleep(0.2)

        # Filter by start_time and remove duplicates
        if start_time:
            all_candles = [c for c in all_candles if c["timestamp"] >= start_time]

        # Remove duplicates and sort
        seen = set()
        unique = []
        for c in sorted(all_candles, key=lambda x: x["timestamp"]):
            if c["timestamp"] not in seen:
                seen.add(c["timestamp"])
                unique.append(c)

        return unique

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_instruments(self) -> List[Dict[str, Any]]:
        """Get available trading instruments with retry"""
        try:
            self._enforce_rate_limit()
            response = self.session.get(f"{self._get_base_url()}/instruments")
            response.raise_for_status()
            data = response.json()
            return data.get("instruments", [])
        except Exception as e:
            print(f"Error getting instruments: {e}")
            return []

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_account_info(self) -> Dict[str, Any]:
        """Get detailed account information with caching"""
        cached = self._get_cached("account_info")
        if cached is not None:
            return cached

        try:
            self._enforce_rate_limit()
            # Get balance info
            balance_resp = self.session.get(f"{self._get_base_url()}/balance")
            balance_resp.raise_for_status()
            balance_data = balance_resp.json()

            self._enforce_rate_limit()
            # Get account/server info for leverage
            server_resp = self.session.get(f"{self._get_base_url()}/server")
            server_data = {}
            leverage = 0
            try:
                server_resp.raise_for_status()
                resp_json = server_resp.json()
                server_data = resp_json.get("server", {})
                leverage = int(server_data.get("leverage", 0))
            except:
                pass

            # If no leverage from server, try to calculate from balance/margin
            if leverage == 0:
                balance_val = float(balance_data.get("balance", 0))
                margin_val = float(balance_data.get("margin", 0))
                if margin_val > 0 and balance_val > 0:
                    leverage = int(balance_val / margin_val * 100)

            # Default leverage if still 0
            if leverage == 0:
                leverage = 200  # Default reasonable value

            # Normalize the response to match expected format
            result = {
                "login": self.config.account_id,
                "balance": float(balance_data.get("balance", 0)),
                "equity": float(balance_data.get("equity", 0)),
                "margin": float(balance_data.get("margin", 0)),
                "free_margin": float(balance_data.get("free_margin", 0)),
                "margin_level": float(balance_data.get("margin_level", 0)),
                "leverage": leverage,
                "currency": server_data.get("currency", "USD")
                if server_data
                else "USD",
                "server": server_data.get("name", self.config.server)
                if server_data
                else self.config.server,
                "raw_balance": balance_data,
                "raw_server": server_data,
            }
            self._set_cached("account_info", result)
            return result
        except Exception as e:
            print(f"Error getting account info: {e}")
            # Return defaults
            return {
                "login": self.config.account_id,
                "balance": 0.0,
                "equity": 0.0,
                "margin": 0.0,
                "free_margin": 0.0,
                "leverage": 0,
                "currency": "USD",
                "server": self.config.server,
            }

    @retry_with_backoff(max_retries=3, backoff_factor=1.0)
    def get_margin_info(self) -> Dict[str, float]:
        """Get margin information with caching"""
        cached = self._get_cached("margin")
        if cached is not None:
            return cached

        try:
            self._enforce_rate_limit()
            response = self.session.get(f"{self._get_base_url()}/balance")
            response.raise_for_status()
            data = response.json()
            result = {
                "balance": float(data.get("balance", 0)),
                "equity": float(data.get("equity", 0)),
                "margin": float(data.get("margin", 0)),
                "free_margin": float(data.get("free_margin", 0)),
                "margin_level": float(data.get("margin_level", 0)),
            }
            self._set_cached("margin", result)
            return result
        except Exception as e:
            print(f"Error getting margin info: {e}")
            return {}


# Factory function
def create_exness_web_provider(
    account_id: int, token: str, server: str = "trial6"
) -> ExnessWebProvider:
    """
    Create Exness Web Provider

    Args:
        account_id: Your Exness account number
        token: JWT token from browser (get from dev tools)
        server: Server code (trial6, trial5, real17, etc)

    How to get token:
    1. Login to my.exness.com
    2. Open Web Terminal
    3. Open Dev Tools (F12)
    4. Look for API requests
    5. Copy Authorization header Bearer token
    """
    config = ExnessConfig(account_id=account_id, token=token, server=server)
    return ExnessWebProvider(config)
