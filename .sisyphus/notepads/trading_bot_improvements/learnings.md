## 2026-03-07
- Added `AsyncExchange` ABC in `trading_bot/exchange/async_base.py` with async-only core market/account methods to enable non-blocking provider implementations.
- Kept method surface minimal (`get_price`, `get_positions`, `get_balance`, `open_position`, `close_position`) so future async providers can be swapped behind one contract without introducing transport-specific dependencies.
