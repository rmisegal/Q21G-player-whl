#!/usr/bin/env python3
"""Q21 Player SDK entry point.

Usage:
    python run.py --scan                    # Single scan
    python run.py --watch                   # Continuous mode (poll every 30s)
    python run.py --watch -p 10             # Poll every 10s
    python run.py --watch --demo            # Continuous with DemoAI
"""
import importlib
import json
import os
import sys
from pathlib import Path


def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


_load_env()


def show_help():
    print("""
Q21 Player SDK

Usage:
    python run.py --scan                    # Single scan
    python run.py --watch                   # Continuous mode (poll every 30s)
    python run.py --watch -p 10             # Poll every 10s
    python run.py --watch --demo            # Continuous with DemoAI

Options:
    --scan              Process messages once and exit
    --watch             Continuously poll for messages
    --demo              Use DemoAI instead of your PlayerAI
    -p, --poll-interval Seconds between scans (default: 30)
    --help, -h          Show this help message
""")


def _load_config() -> dict:
    with open(Path(__file__).parent / "js" / "config.json") as f:
        return json.load(f)


def _create_player_ai(config: dict):
    if os.environ.get("DEMO_MODE"):
        from _infra.demo_ai import DemoAI
        return DemoAI()
    mod = importlib.import_module(config["app"]["player_ai_module"])
    return getattr(mod, config["app"]["player_ai_class"])()


def _parse_poll_interval(args: list) -> int:
    for flag in ("-p", "--poll-interval"):
        if flag in args:
            return int(args[args.index(flag) + 1])
    return 30


def main():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        show_help()
        return 0

    if "--demo" in args:
        args.remove("--demo")
        os.environ["DEMO_MODE"] = "true"
        print("[Demo Mode] Using DemoAI")

    if "--scan" in args and "--watch" not in args:
        print("[Note] Single scan. For continuous, use --watch")

    poll_interval = _parse_poll_interval(args)

    try:
        config = _load_config()
        from q21_player._infra.gmail.client import GmailClient
        from q21_player._infra.gmail.sender import GmailSender
        from _infra.router import MessageRouter
        from _infra.bridge.scan_loop import scan_once, watch

        client = GmailClient()
        client.connect()
        gmail_sender = GmailSender(client)

        player_email = client.get_profile()["emailAddress"]
        player_name = config["player"]["display_name"]
        manager_email = config["league"]["manager_email"]
        player_ai = _create_player_ai(config)

        router = MessageRouter(
            player_email=player_email,
            player_name=player_name,
            player_ai=player_ai,
        )

        if "--watch" in args:
            watch(client, gmail_sender, router, manager_email, poll_interval)
        elif "--scan" in args:
            stats = scan_once(client, gmail_sender, router, manager_email)
            print(f"Done: {stats.found} found, {stats.processed} processed, "
                  f"{stats.sent} sent, {len(stats.errors)} errors")
        return 0

    except ImportError as e:
        print(f"Error: {e}. Run: pip install dist/q21_player-*.whl")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
