"""
Enhanced Exness Web Provider with Complete Order Management
Adds missing endpoints: modify/cancel orders, order history, deals
"""

import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from trading_bot.exchange.exness_web import ExnessWebProvider


class EnhancedExnessProvider(ExnessWebProvider):
    """
    Extended Exness provider with full order lifecycle management
    """
    
    # Order states
    ORDER_STATE_PENDING = 1
    ORDER_STATE_FILLED = 2
    ORDER_STATE_CANCELED = 3
    
    def get_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get pending orders
        
        Endpoint: GET /v1/accounts/{id}/orders
        """
        try:
            url = f"{self._get_base_url()}/orders"
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            orders = data.get("orders", [])
            if symbol:
                orders = [o for o in orders if o.get("instrument") == symbol]
            return orders
            
        except Exception as e:
            print(f"Error getting orders: {e}")
            return []
    
    def modify_order(
        self,
        order_id: str,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        volume: Optional[float] = None
    ) -> bool:
        """
        Modify pending order
        
        Endpoint: PATCH /v1/accounts/{id}/orders/{order_id}
        """
        try:
            url = f"{self._get_base_url()}/orders/{order_id}"
            
            payload = {}
            if price is not None:
                payload["price"] = price
            if sl is not None:
                payload["sl"] = sl
            if tp is not None:
                payload["tp"] = tp
            if volume is not None:
                payload["volume"] = volume
                
            response = self.session.patch(url, json=payload)
            response.raise_for_status()
            
            print(f"✅ Modified order #{order_id}")
            return True
            
        except Exception as e:
            print(f"Error modifying order: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel pending order
        
        Endpoint: DELETE /v1/accounts/{id}/orders/{order_id}
        """
        try:
            url = f"{self._get_base_url()}/orders/{order_id}"
            response = self.session.delete(url)
            response.raise_for_status()
            
            print(f"✅ Canceled order #{order_id}")
            return True
            
        except Exception as e:
            print(f"Error canceling order: {e}")
            return False
    
    def get_order_history(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """
        Get order history (filled and canceled)
        
        Endpoint: GET /v1/accounts/{id}/orders/history
        """
        try:
            url = f"{self._get_base_url()}/orders/history"
            
            params = {}
            if from_date:
                params["from"] = int(from_date.timestamp() * 1000)
            if to_date:
                params["to"] = int(to_date.timestamp() * 1000)
                
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            orders = data.get("orders", [])
            if symbol:
                orders = [o for o in orders if o.get("instrument") == symbol]
            return orders
            
        except Exception as e:
            print(f"Error getting order history: {e}")
            return []
    
    def get_deals(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """
        Get deal history (executed trades)
        
        Endpoint: GET /v1/accounts/{id}/deals
        """
        try:
            url = f"{self._get_base_url()}/deals"
            
            params = {}
            if from_date:
                params["from"] = int(from_date.timestamp() * 1000)
            if to_date:
                params["to"] = int(to_date.timestamp() * 1000)
                
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            deals = data.get("deals", [])
            if symbol:
                deals = [d for d in deals if d.get("instrument") == symbol]
            return deals
            
        except Exception as e:
            print(f"Error getting deals: {e}")
            return []
    
    def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        """
        Get detailed symbol specifications
        
        Endpoint: GET /v1/accounts/{id}/instruments/{symbol}
        """
        try:
            url = f"{self._get_base_url()}/instruments/{symbol}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Error getting symbol specs: {e}")
            return {}
    
    def get_ticks(self, symbol: str, count: int = 100) -> List[Dict]:
        """
        Get recent tick data (level 1)
        
        Note: Exness doesn't provide raw ticks, we use 1-minute candles
        """
        return self.get_candles(symbol, timeframe="1m", limit=count)
    
    def place_pending_order(
        self,
        symbol: str,
        order_type: str,  # buy_limit, sell_limit, buy_stop, sell_stop
        volume: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        expiration: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Place pending order (limit/stop)
        
        Order types:
        - buy_limit (2): Buy when price drops to level
        - sell_limit (3): Sell when price rises to level
        - buy_stop (4): Buy when price rises above level
        - sell_stop (5): Sell when price drops below level
        """
        type_map = {
            "buy_limit": 2,
            "sell_limit": 3,
            "buy_stop": 4,
            "sell_stop": 5
        }
        
        order_type_code = type_map.get(order_type)
        if order_type_code is None:
            print(f"Invalid order type: {order_type}")
            return None
            
        return self._place_order(
            symbol=symbol,
            order_type=order_type_code,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp
        )
    
    def partial_close(self, position_id: str, volume: float) -> bool:
        """
        Partially close a position
        
        Note: Exness may handle this as opening opposite position
        """
        try:
            # Get position details
            positions = self.get_positions()
            pos = next((p for p in positions if p.id == position_id), None)
            
            if not pos:
                print(f"Position #{position_id} not found")
                return False
                
            # Open opposite position with specified volume
            opposite_side = "short" if pos.side == "long" else "long"
            
            ticket = self.open_position(
                symbol=pos.symbol,
                side=opposite_side,
                volume=volume,
                sl=0,
                tp=0
            )
            
            return ticket is not None
            
        except Exception as e:
            print(f"Error partial closing: {e}")
            return False
    
    def close_all_positions(self, symbol: Optional[str] = None) -> int:
        """Close all positions for symbol (or all if no symbol)"""
        positions = self.get_positions(symbol)
        closed = 0
        
        for pos in positions:
            if self.close_position(pos.id, pos.symbol):
                closed += 1
                
        print(f"✅ Closed {closed} positions")
        return closed
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get comprehensive account summary"""
        margin = self.get_margin_info()
        
        # Calculate additional metrics
        balance = margin.get("balance", 0)
        equity = margin.get("equity", 0)
        margin_used = margin.get("margin", 0)
        
        free_margin = equity - margin_used if equity and margin_used else 0
        margin_level = (equity / margin_used * 100) if margin_used > 0 else 0
        
        return {
            "balance": balance,
            "equity": equity,
            "margin_used": margin_used,
            "free_margin": free_margin,
            "margin_level": margin_level,
            "unrealized_pnl": equity - balance,
            "open_positions": len(self.get_positions()),
            "pending_orders": len(self.get_orders())
        }
