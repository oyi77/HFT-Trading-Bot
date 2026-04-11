"""
HFT BOT PLATFORM LAUNCHER — The Master Orchestrator.
Manages all sub-services: Trading Engine, Telegram C2, and Dashboard.
Usage: python platform_launcher.py
"""
import subprocess
import time
import sys
import os
from datetime import datetime

# Setup paths
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(REPO_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

class HFTPlatform:
    def __init__(self):
        self.services = {
            "Telegram_C2": ["python3", "tools/telegram_bot.py"],
            "Maintainer": ["python3", "agent_maintainer/agent.py"],
            "Market_Monitor": ["python3", "tools/live_monitor.py"]
        }
        self.processes = {}

    def start_service(self, name, command):
        print(f"🚀 Starting {name}...")
        log_file = open(f"logs/{name.lower()}.log", "a")
        proc = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=log_file,
            cwd=REPO_ROOT
        )
        self.processes[name] = proc

    def stop_all(self):
        print("\n🛑 Shutting down all services...")
        for name, proc in self.processes.items():
            print(f"Stopping {name}...")
            proc.terminate()
        print("✅ System Halted.")

    def run(self):
        print(f"{'='*40}")
        print(f"💎 BERKAHKARYA HFT PLATFORM 💎")
        print(f"Version: 2.0 (Autonomous Edition)")
        print(f"Start Time: {datetime.now()}")
        print(f"{'='*40}")

        # Start Services
        for name, cmd in self.services.items():
            self.start_service(name, cmd)

        print("\n✅ System is LIVE. Monitoring services...")
        try:
            while True:
                for name, proc in self.processes.items():
                    if proc.poll() is not None:
                        print(f"⚠️ {name} CRASHED! Restarting...")
                        self.start_service(name, self.services[name])
                time.sleep(10)
        except KeyboardInterrupt:
            self.stop_all()

if __name__ == "__main__":
    platform = HFTPlatform()
    platform.run()
