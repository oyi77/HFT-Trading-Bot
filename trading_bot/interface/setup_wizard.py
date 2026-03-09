"""
Setup Wizard - Interactive configuration for trading bot
Works with both CLI and TUI interfaces
"""

import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass, fields

from trading_bot.interface.base import InterfaceConfig


class SetupWizard:
    """Interactive setup wizard for configuring the trading bot"""

    def __init__(self, use_rich: bool = False):
        self.use_rich = use_rich
        self.config = InterfaceConfig()

    def run(self) -> Optional[InterfaceConfig]:
        """
        Run the setup wizard and return configuration
        Returns None if user cancels
        """
        try:
            self._show_welcome()

            # Step 1: Select trading mode
            if not self._select_mode():
                return None

            # Step 2: Select provider
            if not self._select_provider():
                return None

            # Step 3: Authentication (if needed)
            if self.config.mode != "paper":
                if not self._configure_auth():
                    return None

            # Step 4: Trading parameters
            if not self._configure_trading_params():
                return None

            # Step 5: Review
            if not self._review_config():
                return None

            return self.config

        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            return None

    def _show_welcome(self):
        """Show welcome banner"""
        print("\n" + "=" * 70)
        print("🤖  TRADING BOT SETUP WIZARD")
        print("=" * 70)
        print("\nConfigure your trading session step by step.")
        print("Press Ctrl+C at any time to cancel.\n")

    def _select_mode(self) -> bool:
        """Select trading mode"""
        print("\n📋 STEP 1: Select Trading Mode")
        print("-" * 40)
        print("1. 📘 PAPER    - Pure simulation (no account needed)")
        print("2. 📗 FRONTEST - Demo account with real broker data")
        print("3. 📕 REAL     - Real account (⚠️ REAL MONEY!)")
        print("4. ❌ Cancel")

        while True:
            choice = input("\nEnter choice [1-4]: ").strip()
            if choice == "1":
                self.config.mode = "paper"
                self.config.account = "demo"
                return True
            elif choice == "2":
                self.config.mode = "frontest"
                self.config.account = "demo"
                return True
            elif choice == "3":
                self.config.mode = "real"
                self.config.account = "real"
                return True
            elif choice == "4":
                return False
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")

    def _select_provider(self) -> bool:
        """Select exchange provider"""
        print("\n🏦 STEP 2: Select Exchange Provider")
        print("-" * 40)
        print("1. 🏦 Exness   - Forex/CFDs via Web Trading API")
        print("2. 💱 CCXT     - Crypto exchanges (Binance, Bybit, OKX)")
        print("3. ⛽ Ostium   - DEX on Arbitrum (Crypto)")
        print("4. ⬅️  Back")

        while True:
            choice = input("\nEnter choice [1-4]: ").strip()
            if choice == "1":
                self.config.provider = "exness"
                return True
            elif choice == "2":
                self.config.provider = "ccxt"
                # Ask for exchange name
                print("\nSelect CCXT Exchange:")
                print("1. Binance")
                print("2. Bybit")
                print("3. OKX")
                print("4. KuCoin")
                ex_choice = input("Enter choice [1-4]: ").strip()
                exchanges = {"1": "binance", "2": "bybit", "3": "okx", "4": "kucoin"}
                self.config.exchange = exchanges.get(ex_choice, "binance")
                return True
            elif choice == "3":
                self.config.provider = "ostium"
                return True
            elif choice == "4":
                return False
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")

    def _configure_auth(self) -> bool:
        """Configure authentication"""
        print(f"\n🔐 STEP 3: Authentication ({self.config.mode.upper()} Mode)")
        print("-" * 40)

        if self.config.provider == "exness":
            print("\nExness Web Trading API Credentials:")
            print("(Leave empty for defaults where shown)\n")

            try:
                account_id_input = input(f"Account ID [413461571]: ").strip()
                account_id = int(account_id_input) if account_id_input else 413461571
            except ValueError:
                print("⚠️  Invalid account ID, using default: 413461571")
                account_id = 413461571

            server = input("Server [trial6]: ").strip() or "trial6"

            print("\nJWT Token (paste your token and press Enter):")
            print("Tip: You can paste long tokens - they will be accepted.")
            try:
                token = input("Token: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n⚠️  Input cancelled.")
                return False

            self.config.credentials = {
                "account_id": account_id,
                "server": server,
                "token": token,
            }

            if not token:
                print("\n⚠️  Warning: JWT Token is required for live/frontest mode!")
                try:
                    proceed = input("Continue anyway? [y/N]: ").strip().lower()
                    if proceed != "y":
                        return False
                except (EOFError, KeyboardInterrupt):
                    return False

        elif self.config.provider == "ccxt":
            print(f"\n{self.config.exchange.upper()} API Credentials:")

            try:
                api_key = input("API Key: ").strip()
                api_secret = input("API Secret: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n⚠️  Input cancelled.")
                return False

            self.config.credentials = {
                "exchange": self.config.exchange,
                "api_key": api_key,
                "api_secret": api_secret,
                "sandbox": self.config.mode != "real",
            }

            if not api_key:
                print("\n⚠️  Warning: API Key is required!")
                try:
                    proceed = input("Continue anyway? [y/N]: ").strip().lower()
                    if proceed != "y":
                        return False
                except (EOFError, KeyboardInterrupt):
                    return False

        elif self.config.provider == "ostium":
            print(f"\n📦 Ostium DEX Configuration:")
            print("(Uses environment variables - OSTIUM_PRIVATE_KEY)")
            print(
                f"Chain: {'421614 (Sepolia Testnet)' if self.config.mode == 'frontest' else '42161 (Arbitrum Mainnet)'}"
            )

            # Check if private key is set
            import os

            private_key = os.getenv("OSTIUM_PRIVATE_KEY")
            if not private_key:
                print("\n⚠️  Warning: OSTIUM_PRIVATE_KEY not set in environment!")
                print("Set it with: export OSTIUM_PRIVATE_KEY='your_key'")
                try:
                    proceed = input("Continue anyway? [y/N]: ").strip().lower()
                    if proceed != "y":
                        return False
                except (EOFError, KeyboardInterrupt):
                    return False
            else:
                print(f"✓ Private key detected (length: {len(private_key)})")

        return True

    def _configure_trading_params(self) -> bool:
        """Configure trading parameters"""
        print("\n⚙️  STEP 4: Trading Parameters")
        print("-" * 40)

        # Symbol
        symbol = input(f"\nTrading Symbol [{self.config.symbol}]: ").strip()
        if symbol:
            self.config.symbol = symbol.upper()

        # Strategy
        print("\nSelect Strategy:")
        print("1. XAU Hedging (Recommended for XAU/USD)")
        print("2. XAU Hedging V2")
        print("3. Grid Trading")
        print("4. Trend Following")

        strategy_choice = input("Enter choice [1-4] [1]: ").strip() or "1"
        strategies = {
            "1": "xau_hedging",
            "2": "xau_hedging_v2",
            "3": "grid",
            "4": "trend",
        }
        self.config.strategy = strategies.get(strategy_choice, "xau_hedging")

        # Lot size
        lot = input(f"\nLot Size [{self.config.lot}]: ").strip()
        if lot:
            try:
                self.config.lot = float(lot)
            except ValueError:
                print(f"Invalid lot size, using default: {self.config.lot}")

        # Leverage
        leverage = input(f"Leverage [1:{self.config.leverage}]: ").strip()
        if leverage:
            try:
                self.config.leverage = int(leverage)
            except ValueError:
                pass

        # Stop Loss
        sl = input(f"Stop Loss (pips) [{self.config.sl_pips}]: ").strip()
        if sl:
            try:
                self.config.sl_pips = float(sl)
            except ValueError:
                pass

        # Take Profit
        tp = input(f"Take Profit (pips) [{self.config.tp_pips}]: ").strip()
        if tp:
            try:
                self.config.tp_pips = float(tp)
            except ValueError:
                pass

        # Paper-specific settings
        if self.config.mode == "paper":
            print("\n📊 Paper Trading Settings:")

            balance = input(f"Virtual Balance (${self.config.balance}): ").strip()
            if balance:
                try:
                    self.config.balance = float(balance)
                except ValueError:
                    pass

            days = input(f"Simulation Days ({self.config.days}): ").strip()
            if days:
                try:
                    self.config.days = int(days)
                except ValueError:
                    pass

        return True

    def _review_config(self) -> bool:
        """Review configuration before starting"""
        print("\n" + "=" * 70)
        print("📋 STEP 5: Review Configuration")
        print("=" * 70)

        # Mode indicator
        mode_colors = {
            "paper": "📘 PAPER (Simulation)",
            "frontest": "📗 FRONTEST (Demo)",
            "real": "📕 REAL (LIVE MONEY!)",
        }
        print(f"\nTrading Mode: {mode_colors.get(self.config.mode, self.config.mode)}")

        print(f"\nProvider & Account:")
        print(f"  Provider: {self.config.provider.upper()}")
        print(f"  Account: {self.config.account.upper()}")

        if self.config.mode != "paper" and self.config.credentials:
            creds = self.config.credentials
            if self.config.provider == "exness":
                print(f"  Account ID: {creds.get('account_id', 'N/A')}")
                print(f"  Server: {creds.get('server', 'N/A')}")
                # Show token status (masked)
                token = creds.get("token", "")
                if token:
                    masked = (
                        token[:10] + "..." + token[-10:] if len(token) > 30 else "[SET]"
                    )
                    print(f"  JWT Token: {masked}")
                else:
                    print(f"  JWT Token: [NOT SET]")
            elif self.config.provider == "ccxt":
                print(f"  Exchange: {creds.get('exchange', 'N/A').upper()}")
                print(f"  Sandbox: {'Yes' if creds.get('sandbox') else 'No'}")

        print(f"\nTrading Parameters:")
        print(f"  Symbol: {self.config.symbol}")
        print(f"  Strategy: {self.config.strategy}")
        print(f"  Lot Size: {self.config.lot}")
        print(f"  Leverage: 1:{self.config.leverage}")
        print(f"  Stop Loss: {self.config.sl_pips} pips")
        print(f"  Take Profit: {self.config.tp_pips} pips")

        if self.config.mode == "paper":
            print(f"\nPaper Trading Settings:")
            print(f"  Virtual Balance: ${self.config.balance:.2f}")
            print(f"  Simulation Days: {self.config.days}")

        # Risk warning for real mode
        if self.config.mode == "real":
            print("\n" + "⚠️" * 35)
            print("⚠️  WARNING: You are about to trade with REAL MONEY!")
            print("⚠️  All losses will be real and may exceed your deposit!")
            print("⚠️  Only proceed if you fully understand the risks!")
            print("⚠️" * 35)

        print("\n" + "-" * 70)

        while True:
            choice = input("\nStart trading? [Y/n] or [e]dit: ").strip().lower()
            if choice in ("y", "yes", ""):
                return True
            elif choice == "n":
                return False
            elif choice == "e":
                # Let user reconfigure
                return self._reconfigure()
            else:
                print("Please enter 'Y' to start, 'n' to cancel, or 'e' to edit.")

    def _reconfigure(self) -> bool:
        """Let user select which section to reconfigure"""
        print("\nReconfigure which section?")
        print("1. Trading Mode")
        print("2. Provider")
        print("3. Authentication")
        print("4. Trading Parameters")
        print("5. Back to Review")

        choice = input("\nEnter choice [1-5]: ").strip()

        if choice == "1":
            return self._select_mode() and self._review_config()
        elif choice == "2":
            return self._select_provider() and self._review_config()
        elif choice == "3":
            return self._configure_auth() and self._review_config()
        elif choice == "4":
            return self._configure_trading_params() and self._review_config()
        elif choice == "5":
            return self._review_config()
        else:
            return self._review_config()


def run_setup_wizard() -> Optional[InterfaceConfig]:
    """
    Convenience function to run the setup wizard
    Returns InterfaceConfig or None if cancelled
    """
    wizard = SetupWizard()
    return wizard.run()
