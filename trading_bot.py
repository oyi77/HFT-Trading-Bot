#!/usr/bin/env python3
"""
Trading Bot - Main Entry Point
Supports multiple interfaces: CLI, TUI, Web

Usage:
    python trading_bot.py -i cli [ARGS]     # CLI mode - use arguments only
    python trading_bot.py -i tui            # TUI mode - interactive wizard
    python trading_bot.py -i web            # Web mode - web interface
    python trading_bot.py --help            # Show all options
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_bot.interface import get_interface, InterfaceConfig
from trading_bot.interface.setup_wizard import run_setup_wizard
from trading_bot.trading_engine import TradingEngine


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Trading Bot - Multi-Interface Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Interface Modes:
  CLI (-i cli)     Command line interface - uses arguments only
  TUI (-i tui)     Terminal UI with interactive setup wizard (default)
  WEB (-i web)     Web interface

Examples:
  %(prog)s -i tui                          # TUI with interactive wizard
  %(prog)s -i cli --mode paper --lot 0.02  # CLI with arguments
  %(prog)s -i cli -y                       # CLI auto-start with defaults
  %(prog)s --symbol XAUUSDm --lot 0.02     # Default TUI mode with args
        """,
    )

    # Interface selection
    parser.add_argument(
        "-i",
        "--interface",
        choices=["cli", "tui", "web"],
        default="tui",  # Default to TUI with wizard
        help="User interface type (default: tui)",
    )

    # Auto-start without confirmation (for CLI mode)
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-start without confirmation (CLI mode only)",
    )

    # Trading mode
    parser.add_argument(
        "--mode",
        choices=["paper", "frontest", "real"],
        default="paper",
        help="Trading mode (default: paper)",
    )

    # Trading parameters
    parser.add_argument(
        "--symbol", default="XAUUSDm", help="Trading symbol (default: XAUUSDm)"
    )
    parser.add_argument(
        "--lot", type=float, default=0.01, help="Lot size (default: 0.01)"
    )
    parser.add_argument(
        "--leverage", type=int, default=2000, help="Leverage (default: 2000)"
    )
    parser.add_argument(
        "--sl", type=float, default=500, help="Stop loss in pips (default: 500)"
    )
    parser.add_argument(
        "--tp", type=float, default=1000, help="Take profit in pips (default: 1000)"
    )
    parser.add_argument(
        "--balance", type=float, default=100.0, help="Initial balance (default: 100)"
    )

    # Provider settings
    parser.add_argument(
        "--provider",
        type=str,
        default="exness",
        help="Broker/Exchange provider (e.g. exness,ostium,bybit)",
    )

    # Strategy
    parser.add_argument(
        "--strategy",
        default="xau_hedging",
        help="Trading strategy (default: xau_hedging)",
    )

    # Verbose output
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def create_config_from_args(args) -> InterfaceConfig:
    """Create config from command line arguments"""
    return InterfaceConfig(
        mode=args.mode,
        provider=args.provider,
        symbol=args.symbol,
        lot=args.lot,
        leverage=args.leverage,
        strategy=args.strategy,
        sl_pips=args.sl,
        tp_pips=args.tp,
        balance=args.balance,
    )


def run_cli_mode(args) -> int:
    """Run CLI mode with arguments only"""
    # Create config from args
    config = create_config_from_args(args)

    # Show config summary
    print("\n" + "=" * 60)
    print("🤖 TRADING BOT - CLI Mode")
    print("=" * 60)
    print(f"Mode:      {config.mode.upper()}")
    if config.mode == "frontest":
        if config.provider == "ostium":
            print(f"Provider:  {config.provider} (TESTNET - Real Balance)")
            print(f"Balance:   <Will use actual testnet balance>")
        elif config.provider == "bybit":
            print(f"Provider:  {config.provider} (TESTNET - Real Balance)")
            print(f"Balance:   <Will use actual testnet balance>")
        elif config.provider == "exness":
            print(f"Provider:  {config.provider} (DEMO ACCOUNT)")
            print(f"Balance:   <Will use actual demo balance>")
        else:
            print(f"Provider:  {config.provider}")
            print(f"Balance:   ${config.balance:.2f}")
    elif config.mode == "paper":
        print(f"Provider:  {config.provider} (SIMULATION)")
        print(f"Balance:   ${config.balance:.2f} (virtual)")
    else:
        print(f"Provider:  {config.provider}")
        print(f"Balance:   ${config.balance:.2f}")
    print(f"Symbol:    {config.symbol}")
    print(f"Strategy:  {config.strategy}")
    print(f"Lot:       {config.lot}")
    print(f"SL/TP:     {config.sl_pips}/{config.tp_pips} pips")
    print("=" * 60)

    # Confirm unless -y flag
    if not args.yes:
        try:
            response = input("\nStart trading? [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                print("\nTrading cancelled.")
                return 0
        except KeyboardInterrupt:
            print("\n\nCancelled.")
            return 0

    # Create interface and engine
    try:
        interface = get_interface("cli", config=config)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    engine = TradingEngine(config, interface=interface)

    def on_start(cfg):
        engine.start()

    def on_stop():
        engine.stop()

    interface.set_callbacks(
        on_start=on_start, 
        on_stop=on_stop,
        on_pause=engine.pause,
        on_resume=engine.resume,
        on_close_all=engine.close_all_positions,
        on_close_position=engine.close_position,
        on_config_update=engine.update_config
    )

    try:
        interface.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        engine.stop()

    return 0


def run_tui_mode(args) -> int:
    """Run TUI mode - but use CLI due to Rich BlockingIOError issues"""
    print("\n🚀 Starting Trading Bot...")

    # Check if args are provided - skip wizard if key args are set
    has_required_args = any(
        [
            args.mode,
            args.provider,
            args.symbol,
        ]
    )

    if args.yes or (
        has_required_args
        and all(
            [
                args.mode in ("paper", "frontest", "real"),
                args.provider in ("exness", "ccxt", "ostium", "simulator"),
            ]
        )
    ):
        # Use args directly
        config = create_config_from_args(args)
    else:
        try:
            config = run_setup_wizard()
            if config is None:
                print("\nSetup cancelled. Goodbye!")
                return 0
        except Exception as e:
            print(f"\n❌ Error during setup: {e}", file=sys.stderr)
            return 1

    # Always use CLI due to Rich BlockingIOError issues on this system
    verbose = getattr(args, "verbose", False)
    print(f"Using CLI interface... (verbose={verbose})")
    interface = get_interface("cli", config=config, verbose=verbose)

    # Create engine
    engine = TradingEngine(config, interface=interface)

    def on_start(cfg):
        engine.start()

    def on_stop():
        engine.stop()

    interface.set_callbacks(
        on_start=on_start, 
        on_stop=on_stop,
        on_pause=engine.pause,
        on_resume=engine.resume,
        on_close_all=engine.close_all_positions,
        on_close_position=engine.close_position,
        on_config_update=engine.update_config
    )

    try:
        interface.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        engine.stop()

    return 0


def run_web_mode(args) -> int:
    """Run Web mode"""
    config = create_config_from_args(args)

    print("\n🌐 Web Interface")
    print("-" * 40)
    print("Endpoints: /")
    print("          /health")
    print("          /metrics")
    print("          /logs")

    try:
        interface = get_interface("web", config=config)
    except ImportError as e:
        print(f"Web interface not available: {e}")
        return 1
    except ValueError as e:
        print(f"Web interface error: {e}")
        return 1

    engine = TradingEngine(config, interface=interface)

    def on_start(cfg):
        engine.start()

    def on_stop():
        engine.stop()
        
    def on_restart():
        if interface:
            interface.log("🔄 Initiating Engine Restart...", "warning")
        engine.stop()
        time.sleep(1) # Allow threads to cleanly die
        # Re-sync engine config with interface
        engine.config = interface.config
        engine.start()
        if interface:
            interface.log("✅ Engine Restart Complete.", "success")

    interface.set_callbacks(
        on_start=on_start, 
        on_stop=on_stop,
        on_pause=engine.pause,
        on_resume=engine.resume,
        on_close_all=engine.close_all_positions,
        on_close_position=engine.close_position,
        on_config_update=engine.update_config,
        on_restart=on_restart
    )

    try:
        interface.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        engine.stop()

    return 0


def main():
    """Main entry point"""
    args = parse_args()

    # Route to appropriate interface mode
    if args.interface == "cli":
        return run_cli_mode(args)
    elif args.interface == "tui":
        return run_tui_mode(args)
    elif args.interface == "web":
        return run_web_mode(args)
    else:
        print(f"Unknown interface: {args.interface}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
