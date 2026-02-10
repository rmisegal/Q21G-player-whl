#!/usr/bin/env python3
"""Interactive setup script for Q21 Player SDK.

Generates config.json and .env files based on user input.

Usage:
    python setup_config.py
"""
import json
import os
import sys
from pathlib import Path


def ask(prompt: str, default: str = "", required: bool = True, password: bool = False) -> str:
    """Ask user for input with optional default value."""
    if default:
        display = f"{prompt} [{default}]: "
    else:
        display = f"{prompt}: "

    while True:
        if password:
            import getpass
            value = getpass.getpass(display)
        else:
            value = input(display).strip()

        if not value and default:
            return default
        if value:
            return value
        if not required:
            return ""
        print("  This field is required. Please enter a value.")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask user for yes/no input."""
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("  Please enter 'y' or 'n'.")


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print('=' * 50)


def print_info(text: str) -> None:
    """Print info text."""
    print(f"  {text}")


def main() -> int:
    """Run the interactive setup."""
    print("\n" + "=" * 50)
    print("  Q21 Player SDK - Configuration Setup")
    print("=" * 50)
    print("\nThis script will help you configure your Q21 player.")
    print("Press Enter to accept default values shown in [brackets].\n")

    # Check for existing config
    config_path = Path("js/config.json")
    env_path = Path(".env")

    if config_path.exists():
        if not ask_yes_no("config.json already exists. Overwrite?", default=False):
            print("Setup cancelled.")
            return 0

    # -------------------------------------------------------------------------
    # Player Information
    # -------------------------------------------------------------------------
    print_header("Player Information")
    print_info("Your identity in the Q21 league.\n")

    player_email = ask("Your Gmail address (e.g., student@gmail.com)")
    player_name = ask("Your display name", default=player_email.split("@")[0])
    player_id = ask("Your player ID (provided by instructor)", default=player_email.split("@")[0])

    # -------------------------------------------------------------------------
    # Gmail Configuration
    # -------------------------------------------------------------------------
    print_header("Gmail Configuration")
    print_info("OAuth credentials for reading/sending game emails.")
    print_info("Get credentials.json from Google Cloud Console.\n")

    credentials_path = ask("Path to credentials.json", default="credentials.json")
    token_path = ask("Path to token.json (will be created)", default="token.json")

    # -------------------------------------------------------------------------
    # League Configuration
    # -------------------------------------------------------------------------
    print_header("League Configuration")
    print_info("Information about the Q21 league you're joining.\n")

    league_manager_email = ask("League Manager email (provided by instructor)")
    league_id = ask("League ID", default="LEAGUE001")

    # -------------------------------------------------------------------------
    # Database Configuration
    # -------------------------------------------------------------------------
    print_header("Database Configuration")
    print_info("PostgreSQL database for storing game state.\n")

    use_database = ask_yes_no("Do you have a PostgreSQL database?", default=True)

    if use_database:
        db_host = ask("Database host", default="localhost")
        db_port = ask("Database port", default="5432")
        db_name = ask("Database name", default="q21_player")
        db_user = ask("Database user", default="postgres")
        db_password = ask("Database password", password=True)
    else:
        print_info("Note: Some features may not work without a database.")
        db_host = "localhost"
        db_port = "5432"
        db_name = "q21_player"
        db_user = "postgres"
        db_password = ""

    # -------------------------------------------------------------------------
    # Demo Mode
    # -------------------------------------------------------------------------
    print_header("Demo Mode")
    print_info("Demo mode uses predictable responses for testing.")
    print_info("You can always enable it later with: python run.py --demo\n")

    demo_mode = ask_yes_no("Enable demo mode by default?", default=False)

    # -------------------------------------------------------------------------
    # Generate config.json
    # -------------------------------------------------------------------------
    config = {
        "app": {
            "player_ai_module": "my_player",
            "player_ai_class": "MyPlayerAI",
            "demo_mode": demo_mode
        },
        "gmail": {
            "account": player_email,
            "credentials_path": credentials_path,
            "token_path": token_path
        },
        "database": {
            "host": db_host,
            "port": int(db_port),
            "name": db_name,
            "user": db_user,
            "password": db_password
        },
        "league": {
            "manager_email": league_manager_email,
            "league_id": league_id
        },
        "player": {
            "user_id": player_id,
            "display_name": player_name
        }
    }

    # Ensure js directory exists
    Path("js").mkdir(exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"\n  Created: {config_path}")

    # -------------------------------------------------------------------------
    # Generate .env file
    # -------------------------------------------------------------------------
    env_lines = [
        "# Q21 Player SDK Environment Configuration",
        "# Generated by setup_config.py",
        "",
        "# Gmail Configuration",
        f"GMAIL_ACCOUNT={player_email}",
        f"GMAIL_CREDENTIALS_PATH={credentials_path}",
        f"GMAIL_TOKEN_PATH={token_path}",
        "",
        "# Database Configuration",
        f"GTAI_DB_HOST={db_host}",
        f"GTAI_DB_PORT={db_port}",
        f"GTAI_DB_NAME={db_name}",
        f"GTAI_DB_USER={db_user}",
        f"GTAI_DB_PASSWORD={db_password}",
        "",
        "# App Configuration",
        f"DEMO_MODE={'true' if demo_mode else 'false'}",
        "POLL_INTERVAL_SEC=30",
        "",
        "# LLM Configuration (optional)",
        "# LLM_METHOD=cli",
        "# LLM_DEFAULT_AGENT=CLAUDE_STRATEGY",
        "# LLM_TIMEOUT_SEC=120",
        "",
    ]

    with open(env_path, "w") as f:
        f.write("\n".join(env_lines))

    print(f"  Created: {env_path}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print_header("Setup Complete!")
    print()
    print("  Next steps:")
    print()
    print("  1. Copy your credentials.json to this folder")
    print("     (Download from Google Cloud Console)")
    print()
    print("  2. Test your configuration:")
    print("     python run.py --test-connectivity")
    print()
    print("  3. Run in demo mode to verify everything works:")
    print("     python run.py --scan --demo")
    print()
    print("  4. Implement your AI in my_player.py")
    print()
    print("  5. Run with your implementation:")
    print("     python run.py --scan")
    print()

    # Security reminder
    print_header("Security Reminder")
    print()
    print("  DO NOT commit these files to git:")
    print("    - credentials.json")
    print("    - token.json")
    print("    - .env")
    print("    - js/config.json (contains password)")
    print()
    print("  These are already in .gitignore.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
