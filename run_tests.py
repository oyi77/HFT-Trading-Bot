#!/usr/bin/env python3
"""
Test Runner for Trading Bot

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --quick      # Run only unit tests
    python run_tests.py --coverage   # Run with coverage report
    python run_tests.py --verbose    # Run with verbose output
"""
import sys
import subprocess
import argparse


def run_tests(args):
    """Run pytest with given arguments"""
    cmd = ["python", "-m", "pytest", "tests/"]
    
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-v" if not args.quick else "-q")
    
    if args.quick:
        # Run only unit tests (fast)
        cmd.extend(["-m", "not slow and not integration"])
    
    if args.coverage:
        cmd.extend(["--cov=trading_bot", "--cov-report=term-missing"])
    
    cmd.extend(["--tb=short"])
    
    print("=" * 60)
    print("🧪 RUNNING TRADING BOT TESTS")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd)
    
    print("=" * 60)
    if result.returncode == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ TESTS FAILED (exit code: {result.returncode})")
    print("=" * 60)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Run Trading Bot Tests')
    parser.add_argument('--quick', action='store_true', 
                       help='Run only fast unit tests')
    parser.add_argument('--coverage', action='store_true',
                       help='Generate coverage report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    return run_tests(args)


if __name__ == '__main__':
    sys.exit(main())
