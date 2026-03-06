"""
Exness Web Trading API Provider
Direct integration dengan Exness Web Terminal API berdasarkan traced data.
"""

import requests
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from trading_bot.core.models import Position, Order
from trading_bot.core.interfaces import Exchange


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

    def _get_base_url(self) -> str:
        """Get base URL for account"""
        return f"{self.config.base_url}/{self.config.server}/v1/accounts/{self.config.account_id}"

    def _get_v2_url(self) -> str:
        """Get v2 base URL for candles"""
        return f"{self.config.base_url}/{self.config.server}/v2/accounts/{self.config.account_id}"

    # ==================== Exchange Interface ====================

    def connect(self) -> bool:
        """Test connection by fetching account info"""
        try:
            response = self.session.get(f"{self._get_base_url()}/server")
            response.raise_for_status()
            data = response.json()
            print(f"✅ Connected to Exness {data['server']['name']}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def get_balance(self) -> float:
        """Get account balance"""
        try:
            response = self.session.get(f"{self._get_base_url()}/balance")
            response.raise_for_status()
            data = response.json()
            return float(data.get("balance", 0))
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0

    def get_equity(self) -> float:
        """Get account equity"""
        try:
            response = self.session.get(f"{self._get_base_url()}/balance")
            response.raise_for_status()
            data = response.json()
            return float(data.get("equity", 0))
        except Exception as e:
            print(f"Error getting equity: {e}")
            return 0.0

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions"""
        try:
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

    def close_position(self, position_id: str, symbol: Optional[str] = None) -> bool:
        """Close position by ID"""
        try:
            # Exness uses order to close position
            # Position ID is the ticket to close
            url = f"{self._get_base_url()}/positions/{position_id}"
            response = self.session.delete(url)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error closing position {position_id}: {e}")
            return False

    def modify_position(self, ticket: str, sl: float = None, tp: float = None) -> bool:
        """Modify position SL/TP (implements Exchange interface)"""
        try:
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

    def get_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            # Get latest candle as price reference
            candles = self.get_candles(symbol, timeframe="1m", limit=1)
            if candles:
                return candles[-1]["close"]
            return 0.0
        except Exception as e:
            print(f"Error getting price: {e}")
            return 0.0

    # ==================== Extended Methods ====================

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

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 300,
        price_type: str = "bid",
        from_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get candlestick data

        Args:
            symbol: Trading pair (e.g., XAUUSDm)
            timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d
            limit: Number of candles (max ~1000)
            price_type: bid or ask
            from_time: Timestamp in milliseconds to fetch from (default: latest)
        """
        try:
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

    def get_instruments(self) -> List[Dict[str, Any]]:
        """Get available trading instruments"""
        try:
            response = self.session.get(f"{self._get_base_url()}/instruments")
            response.raise_for_status()
            data = response.json()
            return data.get("instruments", [])
        except Exception as e:
            print(f"Error getting instruments: {e}")
            return []

    def get_account_info(self) -> Dict[str, Any]:
        """Get detailed account information"""
        try:
            # Get balance info
            balance_resp = self.session.get(f"{self._get_base_url()}/balance")
            balance_resp.raise_for_status()
            balance_data = balance_resp.json()

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
                    # Approximate leverage
                    leverage = int(balance_val / margin_val * 100)

            # Default leverage if still 0
            if leverage == 0:
                leverage = 200  # Default reasonable value

            # Normalize the response to match expected format
            return {
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

    def get_margin_info(self) -> Dict[str, float]:
        """Get margin information"""
        try:
            response = self.session.get(f"{self._get_base_url()}/balance")
            response.raise_for_status()
            data = response.json()
            return {
                "balance": float(data.get("balance", 0)),
                "equity": float(data.get("equity", 0)),
                "margin": float(data.get("margin", 0)),
                "free_margin": float(data.get("free_margin", 0)),
                "margin_level": float(data.get("margin_level", 0)),
            }
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
