"""
Agent Decision Loop — The "Goose" Style Intelligent Agent.
Combines Technical, Macro, and Whale data to make final trade calls.
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_bot.core.macro_intelligence import MacroIntelligence
from trading_bot.core.whale_intelligence import WhaleIntelligence

class TradingAgent:
    def __init__(self):
        self.macro = MacroIntelligence()
        self.whale = WhaleIntelligence()
        
    def analyze_situation(self, technical_signal="NEUTRAL"):
        """
        Final confluence analysis.
        """
        macro_meta = self.macro.get_summary()
        whale_meta = self.whale.get_cot_sentiment()
        
        # Confluence Weighting
        score = 0
        if technical_signal == "BUY": score += 2
        if technical_signal == "SELL": score -= 2
        
        if macro_meta.get("sentiment") == "BULLISH (Macro)": score += 1
        if macro_meta.get("sentiment") == "BEARISH (Macro)": score -= 1
        
        if whale_meta.get("institutional_bias") == "BULLISH": score += 1
        
        decision = "WAIT"
        if score >= 2: decision = "STRONG BUY"
        elif score == 1: decision = "SCALP BUY"
        elif score <= -2: decision = "STRONG SELL"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "final_decision": decision,
            "confidence_score": score,
            "reasoning": {
                "technical": technical_signal,
                "macro": macro_meta.get("sentiment"),
                "whale": whale_meta.get("signal")
            },
            "raw_data": {
                "macro": macro_meta,
                "whale": whale_meta
            }
        }

    def generate_report(self, analysis):
        """Generates a professional Alpha-style report."""
        report = f"""
=== 🤖 {analysis['final_decision']} ADVISORY ===
Time: {analysis['timestamp']}
Score: {analysis['confidence_score']} / 4

[Reasoning]
- Technical Signal: {analysis['reasoning']['technical']}
- Macro Context: {analysis['reasoning']['macro']}
- Whale Flow: {analysis['reasoning']['whale']}

[Market Context]
- DXY: {analysis['raw_data']['macro'].get('dxy', {}).get('value')} ({analysis['raw_data']['macro'].get('dxy', {}).get('signal')})
- Institutional Positioning: {analysis['raw_data']['whale'].get('managed_money_longs')} Longs vs {analysis['raw_data']['whale'].get('managed_money_shorts')} Shorts
================================
"""
        return report

if __name__ == "__main__":
    agent = TradingAgent()
    analysis = agent.analyze_situation(technical_signal="BUY")
    print(agent.generate_report(analysis))
