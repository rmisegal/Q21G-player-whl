#!/usr/bin/env python3
"""Unified setup script for Q21 Player SDK.

Runs all setup steps in the correct order:
1. Gmail OAuth (gets your email automatically)
2. Configuration (pre-fills email from OAuth)
3. Verification

Usage:
    python setup.py
    python setup.py --skip-gmail    # Skip Gmail setup if already done
    python setup.py --skip-verify   # Skip verification step
"""
import argparse
import json
import shutil
import sys
from pathlib import Path


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print('=' * 60)


def print_step(num: int, total: int, text: str) -> None:
    print(f"\n  Step {num}/{total}: {text}")
    print("  " + "-" * 50)


def ask(prompt: str, default: str = "", required: bool = True, password: bool = False) -> str:
    """Ask user for input with optional default value."""
    if default:
        display = f"  {prompt} [{default}]: "
    else:
        display = f"  {prompt}: "

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
        print("    This field is required. Please enter a value.")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask user for yes/no input."""
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"  {prompt} [{default_str}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("    Please enter 'y' or 'n'.")


def check_credentials_file(path: Path) -> bool:
    """Validate that the file looks like Google OAuth credentials."""
    try:
        with open(path) as f:
            data = json.load(f)
        if "installed" in data or "web" in data:
            return True
        print(f"    Warning: {path} doesn't look like Google OAuth credentials.")
        return False
    except json.JSONDecodeError:
        print(f"    Error: {path} is not valid JSON.")
        return False
    except Exception as e:
        print(f"    Error reading {path}: {e}")
        return False


def setup_gmail() -> tuple[bool, str]:
    """Setup Gmail OAuth and return (success, email)."""
    print_header("Gmail OAuth Setup")

    credentials_path = Path("credentials.json")
    token_path = Path("token.json")

    # Check if already set up
    if token_path.exists() and credentials_path.exists():
        print("\n  Gmail credentials already configured.")
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            SCOPES = [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.modify",
            ]

            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if creds and creds.valid:
                service = build("gmail", "v1", credentials=creds)
                profile = service.users().getProfile(userId="me").execute()
                email = profile.get("emailAddress", "")
                print(f"  Already authenticated as: {email}")

                if ask_yes_no("Use this account?", default=True):
                    return True, email
                else:
                    print("  Will re-authenticate...")
        except Exception:
            pass

    # Need to set up credentials
    if not credentials_path.exists():
        print("""
  You need OAuth credentials from Google Cloud Console.

  If you don't have them yet:
    1. Go to https://console.cloud.google.com/
    2. Create a new project (or select existing)
    3. Enable the Gmail API:
       - Go to "APIs & Services" > "Library"
       - Search for "Gmail API" and enable it
    4. Configure OAuth consent screen:
       - Go to "APIs & Services" > "OAuth consent screen"
       - Select "External" > Create
       - Fill required fields, add your email as test user
    5. Create OAuth credentials:
       - Go to "APIs & Services" > "Credentials"
       - Click "Create Credentials" > "OAuth client ID"
       - Choose "Desktop app" as application type
       - Download the JSON file
""")
        source_input = ask("Path to your downloaded credentials JSON file")
        source_path = Path(source_input).expanduser()

        if not source_path.exists():
            print(f"\n    Error: File not found: {source_path}")
            return False, ""

        if not check_credentials_file(source_path):
            return False, ""

        shutil.copy(source_path, credentials_path)
        print(f"  Copied credentials to: {credentials_path}")

    # Run OAuth flow
    print("\n  Starting OAuth flow...")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ]

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("  Refreshing expired token...")
                creds.refresh(Request())
            else:
                print("  Opening browser for Google OAuth consent...")
                print("  (If browser doesn't open, check the URL in terminal)\n")
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        # Get email from profile
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "")

        print(f"\n  Authenticated as: {email}")
        print(f"  Token saved to: {token_path}")

        return True, email

    except ImportError:
        print("    Error: Required packages not installed.")
        print("    Run: pip install google-auth-oauthlib google-api-python-client")
        return False, ""
    except Exception as e:
        print(f"    OAuth flow failed: {e}")
        return False, ""


def setup_config(gmail_account: str = "") -> bool:
    """Setup configuration file."""
    print_header("Player Configuration")

    config_path = Path("js/config.json")

    if config_path.exists():
        if not ask_yes_no("config.json already exists. Overwrite?", default=False):
            print("  Keeping existing configuration.")
            return True

    # Player Information
    print("\n  --- Player Information ---")
    print("  Your identity in the Q21 league.\n")

    if gmail_account:
        print(f"  Gmail account: {gmail_account} (from OAuth)")
        player_email = gmail_account
    else:
        player_email = ask("Your Gmail address")

    default_name = player_email.split("@")[0] if player_email else ""
    player_name = ask("Your display name", default=default_name)
    player_id = ask("Your player ID (from instructor)", default=default_name)

    # League Configuration
    print("\n  --- League Configuration ---")
    print("  Information from your instructor.\n")

    league_manager_email = ask("League Manager email")
    league_id = ask("League ID", default="LEAGUE001")

    # Database Configuration
    print("\n  --- Database Configuration ---")
    print("  PostgreSQL database for storing game state.\n")

    use_database = ask_yes_no("Do you have a PostgreSQL database?", default=True)

    if use_database:
        db_host = ask("Database host", default="localhost")
        db_port = ask("Database port", default="5432")
        db_name = ask("Database name", default="q21_player")
        db_user = ask("Database user", default="postgres")
        db_password = ask("Database password", password=True)
    else:
        print("    Note: Some features may not work without a database.")
        db_host, db_port, db_name, db_user, db_password = "localhost", "5432", "q21_player", "postgres", ""

    # Demo Mode
    print("\n  --- Demo Mode ---")
    demo_mode = ask_yes_no("Enable demo mode by default?", default=False)

    # Generate config
    config = {
        "app": {
            "player_ai_module": "my_player",
            "player_ai_class": "MyPlayerAI",
            "demo_mode": demo_mode
        },
        "gmail": {
            "account": player_email,
            "credentials_path": "credentials.json",
            "token_path": "token.json"
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

    Path("js").mkdir(exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"\n  Created: {config_path}")

    # Generate .env
    env_path = Path(".env")
    env_lines = [
        "# Q21 Player SDK Environment Configuration",
        "",
        "# Gmail",
        f"GMAIL_ACCOUNT={player_email}",
        f"GMAIL_CREDENTIALS_PATH=credentials.json",
        f"GMAIL_TOKEN_PATH=token.json",
        "",
        "# Database",
        f"GTAI_DB_HOST={db_host}",
        f"GTAI_DB_PORT={db_port}",
        f"GTAI_DB_NAME={db_name}",
        f"GTAI_DB_USER={db_user}",
        f"GTAI_DB_PASSWORD={db_password}",
        "",
        "# App",
        f"DEMO_MODE={'true' if demo_mode else 'false'}",
        "",
    ]

    with open(env_path, "w") as f:
        f.write("\n".join(env_lines))

    print(f"  Created: {env_path}")

    return True


def verify_setup() -> bool:
    """Run quick verification."""
    print_header("Verification")

    issues = []

    # Check files
    files_to_check = [
        ("js/config.json", "Configuration"),
        ("credentials.json", "Gmail credentials"),
        ("token.json", "Gmail token"),
        ("my_player.py", "PlayerAI module"),
    ]

    for path, name in files_to_check:
        if Path(path).exists():
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} (missing)")
            issues.append(f"Missing: {path}")

    # Quick Gmail check
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_path = Path("token.json")
        if token_path.exists():
            SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            service = build("gmail", "v1", credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            print(f"  ✓ Gmail API ({profile.get('emailAddress', 'connected')})")
        else:
            issues.append("Gmail not authenticated")
    except Exception as e:
        print(f"  ✗ Gmail API ({e})")
        issues.append(f"Gmail error: {e}")

    if issues:
        print(f"\n  {len(issues)} issue(s) found. Run 'python verify_setup.py' for details.")
        return False

    print("\n  All checks passed!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup Q21 Player SDK")
    parser.add_argument("--skip-gmail", action="store_true", help="Skip Gmail OAuth setup")
    parser.add_argument("--skip-verify", action="store_true", help="Skip verification")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Q21 Player SDK - Setup Wizard")
    print("=" * 60)
    print("\n  This wizard will configure your Q21 player.")
    print("  Press Enter to accept default values shown in [brackets].")

    gmail_account = ""

    # Step 1: Gmail OAuth
    if not args.skip_gmail:
        success, gmail_account = setup_gmail()
        if not success:
            print("\n  Gmail setup failed. You can retry with: python setup_gmail.py")
            if not ask_yes_no("Continue with config setup anyway?", default=False):
                return 1

    # Step 2: Configuration
    if not setup_config(gmail_account):
        return 1

    # Step 3: Verification
    if not args.skip_verify:
        verify_setup()

    # Done
    print_header("Setup Complete!")
    print("""
  Next steps:

  1. Verify full setup:
     python verify_setup.py

  2. Test with demo mode:
     python run.py --scan --demo

  3. Implement your AI in my_player.py

  4. Run with your implementation:
     python run.py --scan
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
