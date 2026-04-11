"""
Live Market Engine - The Pulse of the Platform.
Now fully connected to Paper Trading Execution.
"""
import time
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_bot.core.agent_decision import TradingAgent

class PaperEngine:
    def __init__(self):
        self.agent = TradingAgent()
        self.log_path = "data/paper_trades.jsonl"
        os.makedirs("data", exist_ok=True)

    def execute_logic(self):
        # 1. Analisa Confluence (Technical + Macro + Whale)
        # Note: 'BUY' is passed here as a technical trigger sample
        analysis = self.agent.analyze_situation(technical_signal="NEUTRAL")
        
        decision = analysis['final_decision']
        confidence = analysis['confidence_score']

        print(f"[{datetime.now()}] AI Decision: {decision} (Score: {confidence})")

        # 2. Execution Logic for Paper Trading
        if "STRONG" in decision:
            self.log_trade(decision, analysis['raw_data'])
            return f"🚀 Paper Trade Executed: {decision}"
        
        return "Checking market..."

    def log_trade(self, side, context):
        trade_entry = {
            "timestamp": datetime.now().isoformat(),
            "side": side,
            "symbol": "XAUUSD",
            "price": 2345.67, # In live, fetch from yfinance
            "macro_sentiment": context['macro']['sentiment'],
            "whale_bias": context['whale']['institutional_bias']
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(trade_entry) + "\n")

if __name__ == "__main__":
    engine = PaperEngine()
    print("Paper Trading Engine Initialized...")
    while True:
        status = engine.execute_logic()
        print(status)
        time.sleep(900) # Check every 15 minutes
