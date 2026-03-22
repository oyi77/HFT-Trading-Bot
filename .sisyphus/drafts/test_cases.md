# Test Cases for Trading Bot Improvements

## Test Suite Overview

**Total Tests**: 47 tests across 6 categories  
**Coverage**: Performance, Async, Risk, State, Architecture, Integration

---

## Category 1: Ostium Performance Tests (5 tests)

### T1.1: test_ostium_latency_improvement
```python
def test_ostium_latency_improvement():
    """Verify Ostium price fetch < 100ms after fix"""
    # Setup
    ostium = create_ostium_exchange_test()
    
    # Measure 10 sequential calls
    times = []
    for _ in range(10):
        start = time.time()
        ostium.get_price("XAUUSD")
        times.append(time.time() - start)
    
    avg_time = sum(times) / len(times)
    assert avg_time < 0.1, f"Average latency {avg_time}s exceeds 100ms"
```

### T1.2: test_event_loop_reuse
```python
def test_event_loop_reuse():
    """Verify persistent event loop is reused"""
    ostium = create_ostium_exchange_test()
    
    # Get loop IDs
    loop_id_1 = id(ostium._loop)
    ostium.get_price("XAUUSD")
    loop_id_2 = id(ostium._loop)
    
    assert loop_id_1 == loop_id_2, "Event loop not reused"
```

### T1.3: test_no_new_loops_created
```python
def test_no_new_loops_created():
    """Verify update_price doesn't create new event loops"""
    import asyncio
    
    initial_count = len(asyncio.all_tasks())
    ostium = create_ostium_exchange_test()
    
    # Call 5 times
    for _ in range(5):
        ostium.update_price()
    
    final_count = len(asyncio.all_tasks())
    assert final_count == initial_count, "New event loops created"
```

### T1.4: test_async_context_manager
```python
@pytest.mark.asyncio
async def test_async_context_manager():
    """Test OstiumExchange async context manager"""
    async with OstiumExchange(config) as ostium:
        price = await ostium.get_price("XAUUSD")
        assert price > 0
        assert ostium._loop.is_running()
```

### T1.5: test_concurrent_ostium_calls
```python
@pytest.mark.asyncio
async def test_concurrent_ostium_calls():
    """Test concurrent price fetches don't conflict"""
    ostium = create_ostium_exchange_test()
    
    # Fetch 3 prices concurrently
    tasks = [
        ostium.get_price("XAUUSD"),
        ostium.get_price("XAUUSD"),
        ostium.get_price("XAUUSD"),
    ]
    prices = await asyncio.gather(*tasks)
    
    assert all(p > 0 for p in prices)
    assert len(set(prices)) <= 1  # Same price (cached)
```

---

## Category 2: Async Exchange Tests (8 tests)

### T2.1: test_async_exchange_interface
```python
@pytest.mark.asyncio
async def test_async_exchange_interface():
    """Test AsyncExchange ABC methods are async"""
    class TestAsyncExchange(AsyncExchange):
        async def get_price(self, symbol): return 100.0
        async def get_positions(self): return []
        async def open_position(self, **kwargs): return "pos_1"
    
    exchange = TestAsyncExchange()
    price = await exchange.get_price("XAUUSD")
    assert price == 100.0
```

### T2.2: test_threadpool_wrapper
```python
def test_threadpool_wrapper():
    """Test ThreadPoolExecutor wraps sync methods"""
    from trading_bot.exchange.async_wrapper import AsyncExchangeWrapper
    
    sync_exchange = MockExchange()
    async_exchange = AsyncExchangeWrapper(sync_exchange)
    
    # Should run in thread pool
    price = async_exchange.get_price("XAUUSD")
    assert isinstance(price, concurrent.futures.Future)
```

### T2.3: test_parallel_fetch_performance
```python
@pytest.mark.asyncio
async def test_parallel_fetch_performance():
    """Test parallel fetch reduces total time"""
    async def fetch_all_data(exchange):
        start = time.time()
        results = await asyncio.gather(
            exchange.get_price("XAUUSD"),
            exchange.get_positions(),
            exchange.get_balance(),
        )
        return time.time() - start, results
    
    duration, results = await fetch_all_data(mock_async_exchange)
    
    # Parallel should be ~max latency, not sum
    assert duration < 0.3  # Assuming each call ~100ms
```

### T2.4: test_market_snapshot_method
```python
@pytest.mark.asyncio
async def test_market_snapshot_method():
    """Test get_market_snapshot() returns all data"""
    snapshot = await async_exchange.get_market_snapshot("XAUUSD")
    
    assert "price" in snapshot
    assert "positions" in snapshot
    assert "stats" in snapshot
    assert isinstance(snapshot["price"], float)
```

### T2.5: test_async_error_handling
```python
@pytest.mark.asyncio
async def test_async_error_handling():
    """Test async methods handle exceptions properly"""
    class FailingExchange(AsyncExchange):
        async def get_price(self, symbol):
            raise ConnectionError("Network down")
    
    exchange = FailingExchange()
    
    with pytest.raises(ConnectionError):
        await exchange.get_price("XAUUSD")
```

### T2.6: test_exchange_timeout
```python
@pytest.mark.asyncio
async def test_exchange_timeout():
    """Test async operations timeout correctly"""
    class SlowExchange(AsyncExchange):
        async def get_price(self, symbol):
            await asyncio.sleep(10)  # Very slow
            return 100.0
    
    exchange = SlowExchange()
    
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(exchange.get_price("XAUUSD"), timeout=1.0)
```

### T2.7: test_async_circuit_breaker_integration
```python
@pytest.mark.asyncio
async def test_async_circuit_breaker_integration():
    """Test circuit breaker works with async calls"""
    cb = CircuitBreaker(threshold=3)
    exchange = AsyncExchangeWithCircuitBreaker(exchange, cb)
    
    # Simulate 3 failures
    for _ in range(3):
        with pytest.raises(Exception):
            await exchange.get_price("XAUUSD")
    
    # Circuit should be OPEN
    with pytest.raises(CircuitOpenError):
        await exchange.get_price("XAUUSD")
```

### T2.8: test_async_cleanup
```python
@pytest.mark.asyncio
async def test_async_cleanup():
    """Test proper cleanup of async resources"""
    exchange = AsyncExchange()
    await exchange.connect()
    
    # Do some work
    await exchange.get_price("XAUUSD")
    
    # Cleanup
    await exchange.disconnect()
    assert not exchange.is_connected()
```

---

## Category 3: Circuit Breaker Tests (6 tests)

### T3.1: test_circuit_breaker_states
```python
def test_circuit_breaker_states():
    """Test circuit breaker state transitions"""
    cb = CircuitBreaker(threshold=3, timeout=30)
    
    assert cb.state == CircuitState.CLOSED
    
    # Fail 3 times
    for _ in range(3):
        cb.record_failure()
    
    assert cb.state == CircuitState.OPEN
    
    # Wait for timeout
    time.sleep(31)
    assert cb.state == CircuitState.HALF_OPEN
```

### T3.2: test_circuit_blocks_requests_when_open
```python
def test_circuit_blocks_requests_when_open():
    """Test circuit breaker blocks when OPEN"""
    cb = CircuitBreaker(threshold=1)
    cb.record_failure()
    
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute()
    
    with pytest.raises(CircuitOpenError):
        cb.execute(lambda: "test")
```

### T3.3: test_circuit_half_open_recovery
```python
def test_circuit_half_open_recovery():
    """Test recovery from HALF_OPEN to CLOSED"""
    cb = CircuitBreaker(threshold=1, timeout=1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    
    # Wait for timeout
    time.sleep(1.1)
    
    # Success in HALF_OPEN should close circuit
    result = cb.execute(lambda: "success")
    assert cb.state == CircuitState.CLOSED
    assert result == "success"
```

### T3.4: test_circuit_half_open_reopen
```python
def test_circuit_half_open_reopen():
    """Test failure in HALF_OPEN reopens circuit"""
    cb = CircuitBreaker(threshold=1, timeout=1)
    cb.record_failure()
    time.sleep(1.1)
    
    # Failure in HALF_OPEN should reopen
    def fail():
        raise Exception("fail")
    
    with pytest.raises(Exception):
        cb.execute(fail)
    
    assert cb.state == CircuitState.OPEN
```

### T3.5: test_circuit_reset_after_success
```python
def test_circuit_reset_after_success():
    """Test failure counter resets after success"""
    cb = CircuitBreaker(threshold=3)
    
    cb.record_failure()
    cb.record_failure()
    assert cb.failure_count == 2
    
    cb.record_success()
    assert cb.failure_count == 0
```

### T3.6: test_circuit_decorator
```python
def test_circuit_decorator():
    """Test @circuit_breaker decorator"""
    cb = CircuitBreaker(threshold=2)
    
    @cb.decorate
    def api_call():
        raise ConnectionError("API down")
    
    # Should fail twice then circuit opens
    for _ in range(2):
        with pytest.raises(ConnectionError):
            api_call()
    
    with pytest.raises(CircuitOpenError):
        api_call()
```

---

## Category 4: Risk Management Tests (7 tests)

### T4.1: test_risk_manager_daily_loss_limit
```python
def test_risk_manager_daily_loss_limit():
    """Test daily loss limit enforcement"""
    rm = RiskManager(max_daily_loss=100.0)
    
    # Simulate $90 loss
    rm.update_pnl(-90.0)
    can_trade, reason = rm.check(1000.0)
    assert can_trade
    
    # Simulate additional $20 loss (total $110)
    rm.update_pnl(-20.0)
    can_trade, reason = rm.check(1000.0)
    assert not can_trade
    assert "daily loss limit" in reason.lower()
```

### T4.2: test_risk_manager_drawdown_limit
```python
def test_risk_manager_drawdown_limit():
    """Test max drawdown enforcement"""
    rm = RiskManager(max_drawdown=0.1)  # 10% max drawdown
    rm.set_peak_equity(1000.0)
    
    # 5% drawdown - should allow
    can_trade, _ = rm.check(950.0)
    assert can_trade
    
    # 15% drawdown - should block
    can_trade, reason = rm.check(850.0)
    assert not can_trade
    assert "drawdown" in reason.lower()
```

### T4.3: test_risk_manager_middleware_enforcement
```python
def test_risk_manager_middleware_enforcement():
    """Test all orders pass through RiskManager"""
    engine = TradingEngine()
    engine.risk_manager = RiskManager(max_daily_loss=50.0)
    
    # Mock high loss
    engine.risk_manager.update_pnl(-60.0)
    
    # Attempt to open position
    action = {"action": "open", "side": "buy", "amount": 0.1}
    result = engine.maybe_execute_order(action)
    
    assert result is None  # Order rejected
    assert engine.stats["orders_blocked_by_risk"] == 1
```

### T4.4: test_pre_trade_validation_chain
```python
def test_pre_trade_validation_chain():
    """Test validator chain rejects invalid orders"""
    validators = [
        PriceValidator(min_price=1000),
        PositionSizeValidator(max_size=1.0),
        BalanceValidator(),
    ]
    
    chain = ValidatorChain(validators)
    
    # Valid order
    order = {"side": "buy", "amount": 0.5, "price": 2000}
    assert chain.validate(order)
    
    # Invalid - too large
    order = {"side": "buy", "amount": 2.0, "price": 2000}
    assert not chain.validate(order)
```

### T4.5: test_position_size_validation
```python
def test_position_size_validation():
    """Test position size limits"""
    validator = PositionSizeValidator(max_size=1.0, min_size=0.01)
    
    assert validator.validate({"amount": 0.5})
    assert not validator.validate({"amount": 2.0})  # Too large
    assert not validator.validate({"amount": 0.001})  # Too small
```

### T4.6: test_price_sanity_check
```python
def test_price_sanity_check():
    """Test price validation rejects unrealistic prices"""
    validator = PriceValidator(min_price=1000, max_price=5000)
    
    assert validator.validate({"price": 2000})
    assert not validator.validate({"price": 100})  # Too low
    assert not validator.validate({"price": 10000})  # Too high
```

### T4.7: test_risk_audit_logging
```python
def test_risk_audit_logging(tmp_path):
    """Test risk decisions are logged"""
    log_file = tmp_path / "risk_audit.log"
    rm = RiskManager(audit_log=log_file)
    
    rm.check(1000.0)  # Allowed
    rm.update_pnl(-1000.0)
    rm.check(1000.0)  # Blocked
    
    log_content = log_file.read_text()
    assert "ALLOWED" in log_content
    assert "BLOCKED" in log_content
```

---

## Category 5: State Persistence Tests (6 tests)

### T5.1: test_state_manager_save_load
```python
def test_state_manager_save_load(tmp_path):
    """Test StateManager saves and loads state"""
    state_file = tmp_path / "state.json"
    sm = StateManager(state_file)
    
    # Save state
    state = {
        "balance": 1000.0,
        "positions": [{"id": "pos_1", "profit": 50.0}],
        "config": {"mode": "paper"},
    }
    sm.save(state)
    
    # Load state
    loaded = sm.load()
    assert loaded["balance"] == 1000.0
    assert loaded["positions"][0]["id"] == "pos_1"
```

### T5.2: test_state_atomic_write
```python
def test_state_atomic_write(tmp_path):
    """Test state file is written atomically"""
    state_file = tmp_path / "state.json"
    backup_file = tmp_path / "state.json.backup"
    
    sm = StateManager(state_file)
    sm.save({"data": "test"})
    
    # Should create backup first
    assert backup_file.exists()
    # Then write main file
    assert state_file.exists()
```

### T5.3: test_state_corruption_recovery
```python
def test_state_corruption_recovery(tmp_path):
    """Test recovery from corrupted state file"""
    state_file = tmp_path / "state.json"
    backup_file = tmp_path / "state.json.backup"
    
    # Create valid backup
    backup_file.write_text('{"balance": 1000}')
    
    # Create corrupted main file
    state_file.write_text("corrupted json{")
    
    sm = StateManager(state_file)
    state = sm.load()
    
    # Should recover from backup
    assert state["balance"] == 1000
```

### T5.4: test_crash_recovery_on_startup
```python
def test_crash_recovery_on_startup(tmp_path):
    """Test bot recovers state on startup"""
    state_file = tmp_path / "state.json"
    
    # Simulate previous crash with saved state
    sm = StateManager(state_file)
    sm.save({
        "balance": 950.0,
        "positions": [{"id": "pos_1", "symbol": "XAUUSD"}],
        "trade_history": [{"pnl": -50.0}],
    })
    
    # Start bot with recovery
    bot = TradingBot()
    bot.recover_state(state_file)
    
    assert bot.balance == 950.0
    assert len(bot.positions) == 1
```

### T5.5: test_state_reconciliation
```python
def test_state_reconciliation():
    """Test reconciliation of saved vs exchange state"""
    # Saved state
    saved_positions = [{"id": "pos_1", "profit": 50}]
    
    # Exchange state (pos_1 was closed externally)
    exchange_positions = []
    
    reconciled = reconcile_state(saved_positions, exchange_positions)
    
    # Should detect missing position
    assert len(reconciled["discrepancies"]) == 1
    assert reconciled["discrepancies"][0]["type"] == "position_missing"
```

### T5.6: test_auto_save_on_trade
```python
def test_auto_save_on_trade(tmp_path):
    """Test state auto-saves after each trade"""
    state_file = tmp_path / "state.json"
    
    engine = TradingEngine()
    engine.enable_auto_save(state_file, interval=1)
    
    # Execute trade
    engine.open_position("XAUUSD", "buy", 0.1)
    
    # Wait for auto-save
    time.sleep(1.1)
    
    # Verify saved
    state = json.loads(state_file.read_text())
    assert len(state["positions"]) == 1
```

---

## Category 6: Architecture Tests (5 tests)

### T6.1: test_single_exchange_abc
```python
def test_single_exchange_abc():
    """Test only one Exchange ABC exists in codebase"""
    import ast
    import glob
    
    exchange_classes = []
    for file in glob.glob("trading_bot/**/*.py", recursive=True):
        with open(file) as f:
            tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if node.name == "Exchange":
                        exchange_classes.append((file, node.bases))
    
    # Should only have one Exchange ABC
    abc_count = sum(1 for _, bases in exchange_classes if any("ABC" in str(b) for b in bases))
    assert abc_count == 1, f"Found {abc_count} Exchange ABCs, expected 1"
```

### T6.2: test_factory_creates_providers
```python
def test_factory_creates_providers():
    """Test factory creates all provider types"""
    from trading_bot.factory import get_exchange
    
    # Test each provider type
    configs = [
        {"type": "exness", "token": "test"},
        {"type": "ostium", "private_key": "0x..."},
        {"type": "simulator"},
    ]
    
    for config in configs:
        exchange = get_exchange(config)
        assert exchange is not None
        assert hasattr(exchange, "connect")
```

### T6.3: test_strategy_factory
```python
def test_strategy_factory():
    """Test factory creates strategies"""
    from trading_bot.factory import get_strategy
    
    strategies = ["xau_hedging", "grid", "trend", "hft"]
    
    for name in strategies:
        strategy = get_strategy(name, config={})
        assert strategy is not None
        assert hasattr(strategy, "on_tick")
```

### T6.4: test_no_duplicate_provider_creation
```python
def test_no_duplicate_provider_creation():
    """Test factory doesn't duplicate provider code"""
    import re
    import glob
    
    # Search for create_*_exchange functions
    creation_patterns = []
    for file in glob.glob("trading_bot/**/*.py", recursive=True):
        with open(file) as f:
            content = f.read()
            matches = re.findall(r"def create_\w+_exchange", content)
            creation_patterns.extend(matches)
    
    # All should be in factory.py
    for pattern in creation_patterns:
        assert "factory" in file, f"{pattern} should be in factory.py"
```

### T6.5: test_consolidated_exchange_interface
```python
def test_consolidated_exchange_interface():
    """Test all providers implement same interface"""
    from trading_bot.exchange.base import Exchange
    from trading_bot.exchange.exness_web import ExnessWebProvider
    from trading_bot.exchange.ostium import OstiumExchange
    from trading_bot.exchange.simulator import SimulatorExchange
    
    providers = [ExnessWebProvider, OstiumExchange, SimulatorExchange]
    
    for provider_class in providers:
        # Check inherits from Exchange
        assert issubclass(provider_class, Exchange)
        
        # Check required methods exist
        required = ["connect", "get_balance", "get_price", "get_positions"]
        for method in required:
            assert hasattr(provider_class, method)
```

---

## Test Execution Order

```
Phase 1: Unit Tests (Fast)
├── Ostium Performance (T1.1 - T1.5)
├── Circuit Breaker (T3.1 - T3.6)
└── Risk Management (T4.1 - T4.7)

Phase 2: Integration Tests (Medium)
├── Async Exchange (T2.1 - T2.8)
└── State Persistence (T5.1 - T5.6)

Phase 3: System Tests (Slow)
└── Architecture (T6.1 - T6.5)

Phase 4: E2E Tests
└── Full workflow with all improvements
```

## Running Tests

```bash
# All tests
python -m pytest tests/improvements/ -v

# Specific category
python -m pytest tests/improvements/test_ostium_performance.py -v
python -m pytest tests/improvements/test_circuit_breaker.py -v
python -m pytest tests/improvements/test_risk_management.py -v

# With coverage
python -m pytest tests/improvements/ --cov=trading_bot --cov-report=html

# Parallel execution
python -m pytest tests/improvements/ -n auto
```

## Expected Results

| Category | Tests | Pass Rate | Coverage |
|----------|-------|-----------|----------|
| Ostium Performance | 5 | 100% | 90%+ |
| Async Exchange | 8 | 100% | 85%+ |
| Circuit Breaker | 6 | 100% | 95%+ |
| Risk Management | 7 | 100% | 90%+ |
| State Persistence | 6 | 100% | 85%+ |
| Architecture | 5 | 100% | 80%+ |
| **Total** | **47** | **100%** | **87%+** |
