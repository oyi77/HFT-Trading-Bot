# HFT Trading Bot - Component Interaction Diagrams

## 1. Current Architecture (Before Improvements)

```mermaid
flowchart TB
    subgraph UI["User Interface"]
        CLI[CLI Interface]
        TUI[TUI Interface]
        WEB[Web Interface]
    end
    
    subgraph Engine["Trading Engine"]
        TE[TradingEngine]
        SR[StrategyRunner]
        RM[RiskManager]
    end
    
    subgraph Strategies["Strategies"]
        XAU[XAUHedgingStrategy]
        GRID[GridStrategy]
        TREND[TrendStrategy]
        HFT[HFTStrategy]
    end
    
    subgraph Exchanges["Exchange Providers"]
        EXNESS[ExnessWebProvider]
        OSTIUM[OstiumExchange]
        BYBIT[BybitExchange]
        CCXT[CCXTExchange]
        SIM[SimulatorExchange]
    end
    
    subgraph Issues["⚠️ Performance Issues"]
        I1[asyncio.run per tick]
        I2[Blocking I/O]
        I3[time.sleep blocking]
        I4[No parallel fetch]
    end
    
    UI --> TE
    TE --> SR
    SR --> Strategies
    SR --> Exchanges
    
    OSTIUM -.- I1
    EXNESS -.- I2
    BYBIT -.- I2
    TE -.- I3
    TE -.- I4
```

## 2. Target Architecture (After Improvements)

```mermaid
flowchart TB
    subgraph UI["User Interface"]
        CLI[CLI Interface]
        TUI[TUI Interface]
        WEB[Web Interface]
    end
    
    subgraph Engine["Trading Engine (Async)"]
        TE[AsyncTradingEngine]
        CB[CircuitBreaker]
        RM[RiskManager Middleware]
        SM[StateManager]
    end
    
    subgraph Strategies["Strategies"]
        XAU[XAUHedgingStrategy]
        GRID[GridStrategy]
        TREND[TrendStrategy]
        HFT[HFTStrategy]
    end
    
    subgraph AsyncLayer["Async Exchange Layer"]
        AE[AsyncExchange ABC]
        TPE[ThreadPoolExecutor]
        CACHE[Price Cache]
    end
    
    subgraph Exchanges["Exchange Providers"]
        EXNESS[ExnessWebProvider]
        OSTIUM[OstiumExchange<br/>Persistent Loop]
        BYBIT[BybitExchange]
        CCXT[CCXTExchange]
        SIM[SimulatorExchange]
    end
    
    subgraph Persistence["State Persistence"]
        DB[(SQLite/JSON)]
        AUDIT[Audit Logs]
    end
    
    UI --> TE
    TE --> CB
    CB --> RM
    RM --> SR[StrategyRunner]
    SR --> Strategies
    
    TE --> AsyncLayer
    AsyncLayer --> Exchanges
    
    TE --> SM
    SM --> Persistence
    
    OSTIUM --> CACHE
    EXNESS --> CACHE
    BYBIT --> CACHE
```

## 3. Async Data Flow (Improved)

```mermaid
sequenceDiagram
    participant TE as TradingEngine
    participant CB as CircuitBreaker
    participant RM as RiskManager
    participant AE as AsyncExchange
    participant TPE as ThreadPool
    participant EX as Exchange
    participant SM as StateManager
    
    TE->>CB: Check circuit state
    CB-->>TE: CLOSED (OK to trade)
    
    par Parallel Data Fetch
        TE->>AE: get_price()
        AE->>TPE: submit(fetch_price)
        TPE->>EX: HTTP Request
        EX-->>TPE: Price Data
        TPE-->>AE: Price
        AE-->>TE: Price
    and
        TE->>AE: get_positions()
        AE->>TPE: submit(fetch_positions)
        TPE->>EX: HTTP Request
        EX-->>TPE: Positions
        TPE-->>AE: Positions
        AE-->>TE: Positions
    and
        TE->>AE: get_stats()
        AE->>TPE: submit(fetch_stats)
        TPE->>EX: HTTP Request
        EX-->>TPE: Stats
        TPE-->>AE: Stats
        AE-->>TE: Stats
    end
    
    TE->>Strategy: on_tick(price, positions, stats)
    Strategy-->>TE: Action Signal
    
    alt Open Position
        TE->>RM: Validate Order
        RM->>RM: Check limits
        RM-->>TE: Approved
        TE->>CB: Record API Call
        TE->>AE: open_position()
        AE->>TPE: submit(order)
        TPE->>EX: Place Order
        EX-->>TPE: Order Result
        TPE-->>AE: Result
        AE-->>TE: Position
        TE->>SM: Save State
        SM->>DB: Persist
    end
```

## 4. Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> CLOSED
    
    CLOSED --> OPEN: 5 consecutive failures
    CLOSED --> CLOSED: Success (reset counter)
    
    OPEN --> HALF_OPEN: Timeout (30s)
    OPEN --> OPEN: Keep blocking
    
    HALF_OPEN --> CLOSED: Success
    HALF_OPEN --> OPEN: Failure
    
    note right of CLOSED
        Normal operation
        All requests pass
    end note
    
    note right of OPEN
        Block all trading
        Return error immediately
    end note
    
    note right of HALF_OPEN
        Test with 1 request
        If success → CLOSED
        If fail → OPEN
    end note
```

## 5. State Persistence Flow

```mermaid
flowchart LR
    subgraph Runtime["Runtime State"]
        B[Balance]
        P[Positions]
        C[Config]
        TH[TradeHistory]
    end
    
    subgraph Save["Save Operation"]
        SM[StateManager]
        SER[Serialize to JSON]
        AT[Atomic Write]
    end
    
    subgraph Storage["Storage"]
        DB[(state.json)]
        BACKUP[(state.json.backup)]
    end
    
    B --> SM
    P --> SM
    C --> SM
    TH --> SM
    
    SM --> SER
    SER --> AT
    AT --> DB
    AT --> BACKUP
    
    style Runtime fill:#e1f5e1
    style Save fill:#fff3cd
    style Storage fill:#f8d7da
```

## 6. Factory Pattern (Post-Refactor)

```mermaid
flowchart TB
    subgraph Factory["trading_bot/factory.py"]
        GF[get_exchange]
        GS[get_strategy]
        GUI[get_interface]
    end
    
    subgraph Config["Configuration"]
        ENV[Environment Variables]
        FILE[Config Files]
    end
    
    subgraph Products["Created Objects"]
        EX[Exchange Providers]
        ST[Strategies]
        UI[Interfaces]
    end
    
    Config --> Factory
    
    GF --> EX
    GS --> ST
    GUI --> UI
    
    EX --> EX1[Exness]
    EX --> EX2[Ostium]
    EX --> EX3[Bybit]
    EX --> EX4[Simulator]
    
    ST --> ST1[XAU Hedging]
    ST --> ST2[Grid]
    ST --> ST3[Trend]
    ST --> ST4[HFT]
```

## 7. Risk Management Flow

```mermaid
flowchart TD
    A[Signal from Strategy] --> B{RiskManager}
    
    B --> C[Daily Loss Check]
    C -->|Pass| D[Drawdown Check]
    C -->|Fail| Z[Reject Order]
    
    D -->|Pass| E[Position Size Check]
    D -->|Fail| Z
    
    E -->|Pass| F[Balance Check]
    E -->|Fail| Z
    
    F -->|Pass| G[Circuit Breaker]
    F -->|Fail| Z
    
    G -->|CLOSED| H[Execute Order]
    G -->|OPEN| Z
    
    H --> I[Log to Audit]
    I --> J[Update State]
    
    Z --> K[Log Rejection]
    
    style H fill:#90EE90
    style Z fill:#FFB6C1
```

## 8. Ostium Async Fix (Detail)

```mermaid
flowchart LR
    subgraph Before["Before (Slow)"]
        A1[update_price call]
        B1[asyncio.run]
        C1[Create new loop]
        D1[Fetch price]
        E1[Close loop]
        
        A1 --> B1 --> C1 --> D1 --> E1
    end
    
    subgraph After["After (Fast)"]
        A2[__init__]
        B2[Create persistent loop]
        C2[update_price call]
        D2[loop.run_in_executor]
        E2[Fetch price]
        
        A2 --> B2
        B2 -.-> C2
        C2 --> D2 --> E2
    end
    
    style Before fill:#FFB6C1
    style After fill:#90EE90
```

## Legend

- **Green boxes**: New/improved components
- **Red boxes**: Problem areas
- **Yellow boxes**: Intermediate processing
- **Solid arrows**: Synchronous calls
- **Dashed arrows**: Async/concurrent calls
- **Par blocks**: Parallel execution
