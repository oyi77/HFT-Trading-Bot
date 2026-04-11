"""
Macro Intelligence Module — The "Bloomberg Terminal" Replacement.
Fetches macro data (DXY, Yields, Fed Rates) to provide context for Gold (XAU) trading.
"""
import os
import pandas as pd
import yfinance as yf
from fredapi import Fred
from datetime import datetime, timedelta

class MacroIntelligence:
    def __init__(self, fred_api_key=None):
        self.fred = Fred(api_key=fred_api_key) if fred_api_key else None
        
    def get_market_proxies(self):
        """
        Get macro proxies via yfinance (no API key needed).
        DX-Y.NYB = Dollar Index
        ^TNX = 10 Year Treasury Yield
        """
        symbols = {
            "DXY": "DX-Y.NYB",
            "US10Y": "^TNX"
        }
        data = {}
        for name, ticker in symbols.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if not hist.empty:
                    data[name] = {
                        "value": round(hist['Close'].iloc[-1], 2),
                        "change": round(hist['Close'].iloc[-1] - hist['Close'].iloc[-2], 3),
                        "signal": "BEARISH for Gold" if (hist['Close'].iloc[-1] > hist['Close'].iloc[-2]) else "BULLISH for Gold"
                    }
            except Exception as e:
                data[name] = {"error": str(e)}
        return data

    def get_fed_data(self):
        """
        Get actual Fed data via FRED API (needs key).
        FEDFUNDS = Effective Federal Funds Rate
        CPIAUCSL = Consumer Price Index
        """
        if not self.fred:
            return {"error": "FRED_API_KEY not provided"}
            
        try:
            fed_funds = self.fred.get_series('FEDFUNDS')
            cpi = self.fred.get_series('CPIAUCSL')
            
            return {
                "fed_funds": fed_funds.iloc[-1],
                "cpi_yoy": round(((cpi.iloc[-1] / cpi.iloc[-13]) - 1) * 100, 2), # YoY inflation
                "status": "Tightening" if fed_funds.iloc[-1] > fed_funds.iloc[-2] else "Easing/Neutral"
            }
        except Exception as e:
            return {"error": str(e)}

    def get_summary(self):
        proxies = self.get_market_proxies()
        fed = self.get_fed_data()
        
        # Simple sentiment logic
        bullish_votes = 0
        if proxies.get("DXY", {}).get("change", 0) < 0: bullish_votes += 1
        if proxies.get("US10Y", {}).get("change", 0) < 0: bullish_votes += 1
        
        sentiment = "NEUTRAL"
        if bullish_votes == 2: sentiment = "BULLISH (Macro)"
        elif bullish_votes == 0: sentiment = "BEARISH (Macro)"
        
        return {
            "sentiment": sentiment,
            "dxy": proxies.get("DXY"),
            "us10y": proxies.get("US10Y"),
            "fed": fed
        }

if __name__ == "__main__":
    # Test run
    macro = MacroIntelligence() # No key test
    print(macro.get_summary())
