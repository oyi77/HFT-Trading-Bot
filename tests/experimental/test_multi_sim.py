from trading_bot.exchange.simulator import SimulatorExchange
from trading_bot.strategy.xau_hedging import XAUHedgingConfig
from dataclasses import dataclass

@dataclass
class DummyConfig:
    provider = ["bybit", "exness"]
    mode = "paper"
    balance = 10000
    symbol = "XAUUSD"

config = DummyConfig()

class DummyEngine:
    def __init__(self):
        self.exchanges = []
        for p in config.provider:
            sim = SimulatorExchange(initial_balance=config.balance, symbol=config.symbol)
            sim.name = p.capitalize()
            self.exchanges.append(sim)
            
    def test_open(self):
        for ex in self.exchanges:
            ex.open_position("XAUUSD", "buy", 0.01)
            
    def update(self):
        aggregated_positions = []
        for ex in self.exchanges:
            broker_name = ex.name
            positions = ex.get_positions()
            for pos in positions:
                try:
                    pos.provider = broker_name
                except Exception as e:
                    print("Error:", e)
            aggregated_positions.extend(positions)
        return aggregated_positions

engine = DummyEngine()
engine.test_open()
positions = engine.update()
print(f"Total positions: {len(positions)}")
for p in positions:
    print(f"Position: Provider={getattr(p, 'provider', 'None')} ID={p.id} ")

