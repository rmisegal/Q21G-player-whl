#!/usr/bin/env python3
"""Q21 Player SDK entry point.

Provides a simple wrapper for the q21-player CLI with demo mode support.

Usage:
    python run.py --scan              # Single scan with your PlayerAI
    python run.py --scan --demo       # Single scan with DemoAI
    python run.py --watch             # Continuous mode with your PlayerAI
    python run.py --watch --demo      # Continuous mode with DemoAI
    python run.py --test-connectivity # Test Gmail and database
"""
import os
import sys


def main():
    """Run the Q21 player with optional demo mode."""
    args = sys.argv[1:]

    # Handle --demo flag
    if "--demo" in args:
        args.remove("--demo")
        os.environ["DEMO_MODE"] = "true"
        print("[Demo Mode] Using DemoAI for predictable responses")

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
