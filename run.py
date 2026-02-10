#!/usr/bin/env python3
"""Q21 Player SDK entry point.

Provides a simple wrapper for the q21-player CLI with demo mode support.

Usage:
    python run.py --scan                    # Single scan (process once and exit)
    python run.py --watch                   # Continuous mode (poll every 30s)
    python run.py --watch -p 10             # Continuous mode (poll every 10s)
    python run.py --watch --demo            # Continuous mode with DemoAI
    python run.py --test-connectivity       # Test Gmail and database

Options:
    --scan              Process messages once and exit
    --watch             Continuously poll for messages
    --demo              Use DemoAI instead of your PlayerAI
    -p, --poll-interval Seconds between scans (default: 30)
    --test-connectivity Test Gmail and database connection
"""
import os
import sys


def show_help():
    """Show usage help."""
    print("""
Q21 Player SDK

Usage:
    python run.py --scan                    # Single scan (process once and exit)
    python run.py --watch                   # Continuous mode (poll every 30s)
    python run.py --watch -p 10             # Continuous mode (poll every 10s)
    python run.py --watch --demo            # Continuous mode with DemoAI
    python run.py --test-connectivity       # Test Gmail and database

Options:
    --scan              Process messages once and exit
    --watch             Continuously poll for messages (use this for games!)
    --demo              Use DemoAI instead of your PlayerAI
    -p, --poll-interval Seconds between scans (default: 30)
    --test-connectivity Test Gmail and database connection
    --help, -h          Show this help message
""")


def main():
    """Run the Q21 player with optional demo mode."""
    args = sys.argv[1:]

    # Show help if no args or --help
    if not args or "--help" in args or "-h" in args:
        show_help()
        return 0

    # Handle --demo flag
    if "--demo" in args:
        args.remove("--demo")
        os.environ["DEMO_MODE"] = "true"
        print("[Demo Mode] Using DemoAI for predictable responses")

    # Warn if using --scan (single mode)
    if "--scan" in args and "--watch" not in args:
        print("[Note] Using --scan (single scan). For continuous polling, use --watch")

    # Import and run the main CLI
    try:
        from q21_player._infra.cli.main import main as cli_main
        sys.argv = ["q21-player"] + args
        return cli_main()
    except ImportError as e:
        print(f"Error: q21_player package not installed. Run:")
        print(f"  pip install dist/q21_player-1.0.0-py3-none-any.whl")
        return 1


if __name__ == "__main__":
    sys.exit(main())
