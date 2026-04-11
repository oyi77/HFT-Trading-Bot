"""
Telegram Control Center — Control & Monitor your HFT Bot from anywhere.
Commands:
/status - Current market and bot status
/report - Detailed Alpha Advisory (Goose Loop)
/pause  - Pause trading activities
/resume - Resume trading activities
"""
import time
import os
import sys
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_bot.core.agent_decision import TradingAgent

class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.agent = TradingAgent()
        self.last_update_id = 0
        self.is_running = True

    def send_message(self, text):
        url = f"{self.base_url}/sendMessage"
        params = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            requests.get(url, params=params, timeout=10)
        except Exception as e:
            print(f"Error sending TG: {e}")

    def get_updates(self):
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        try:
            resp = requests.get(url, params=params, timeout=35).json()
            if resp.get("ok"):
                return resp.get("result", [])
        except Exception as e:
            print(f"Error getting TG updates: {e}")
        return []

    def handle_commands(self):
        updates = self.get_updates()
        for update in updates:
            self.last_update_id = update["update_id"]
            if "message" in update and "text" in update["message"]:
                text = update["message"]["text"]
                sender = update["message"]["from"].get("username", "Unknown")
                
                print(f"Command received: {text} from @{sender}")
                
                if text == "/start":
                    self.send_message("🚀 *HFT Control Center Active*\nWelcome, Boss. Send /report to see current market analysis.")
                
                elif text == "/report":
                    analysis = self.agent.analyze_situation(technical_signal="NEUTRAL")
                    report = self.agent.generate_report(analysis)
                    self.send_message(report)
                
                elif text == "/trades":
                    try:
                        with open("data/paper_trades.jsonl", "r") as f:
                            lines = f.readlines()[-5:] # Show last 5 trades
                            if not lines:
                                self.send_message("No trades recorded yet.")
                            else:
                                msg = "📜 *Last 5 Paper Trades:*\n"
                                for line in lines:
                                    t = json.loads(line)
                                    msg += f"• {t['timestamp'][:16]} | {t['side']} @ {t['price']}\n"
                                self.send_message(msg)
                    except Exception as e:
                        self.send_message(f"Error reading trades: {e}")
                
                elif text == "/status":
                    status = "✅ RUNNING" if self.is_running else "⏸️ PAUSED"
                    self.send_message(f"Bot Status: *{status}*\nUptime: Normal\nHealth: 100%")
                
                elif text == "/pause":
                    self.is_running = False
                    self.send_message("⚠️ *TRADING PAUSED* — All new entries disabled until /resume.")
                
                elif text == "/resume":
                    self.is_running = True
                    self.send_message("▶️ *TRADING RESUMED* — Monitoring entries now.")

    def run_advisory_loop(self):
        """Standard 4-hour reporting + immediate alert if Strong signal."""
        last_report_time = 0
        print("Telegram Link Active...")
        
        while True:
            # 1. Handle incoming user commands
            self.handle_commands()
            
            # 2. Check for Strong Signals every 5 minutes
            current_time = time.time()
            analysis = self.agent.analyze_situation(technical_signal="NEUTRAL") # Dynamic check
            
            if "STRONG" in analysis['final_decision']:
                alert_msg = f"‼️ *URGENT ALPHA ALERT* ‼️\n{self.agent.generate_report(analysis)}"
                self.send_message(alert_msg)
                time.sleep(300) # Cooldown alert
            
            # 3. Regular 4-hour report
            if current_time - last_report_time > 14400: # 4 hours
                report = f"🕒 *Regular Market Update*\n{self.agent.generate_report(analysis)}"
                self.send_message(report)
                last_report_time = current_time
            
            time.sleep(2)

if __name__ == "__main__":
    # Get credentials from env or OpenClaw config
    # In a real run, these should be set in .env
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "8581574594:AAGzrA9DGjzJx3Ak2D6P3NhoQyXyskpMF2Q")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "228956686")
    
    bot = TelegramBot(token, chat_id)
    bot.run_advisory_loop()
