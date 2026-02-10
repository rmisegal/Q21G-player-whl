#!/usr/bin/env python3
"""Verification script for Q21 Player SDK setup.

Checks that all components are properly configured:
1. Required files exist
2. Config is valid
3. Gmail API works
4. Database connection works
5. PlayerAI can be loaded

Usage:
    python verify_setup.py
    python verify_setup.py --verbose
"""
import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Optional


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {Colors.RED}✗{Colors.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {Colors.YELLOW}!{Colors.RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {Colors.BLUE}ℹ{Colors.RESET} {msg}")


def header(msg: str) -> None:
    print(f"\n{Colors.BOLD}{msg}{Colors.RESET}")
    print("-" * 50)


class SetupVerifier:
    """Verifies Q21 Player SDK setup."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.config: Optional[dict] = None

    def check_file_exists(self, path: str, name: str, required: bool = True) -> bool:
        """Check if a file exists."""
        if Path(path).exists():
            ok(f"{name}: {path}")
            return True
        if required:
            fail(f"{name}: {path} (not found)")
            self.errors.append(f"Missing {name}: {path}")
        else:
            warn(f"{name}: {path} (not found, optional)")
            self.warnings.append(f"Missing optional {name}: {path}")
        return False

    def check_required_files(self) -> bool:
        """Check that required files exist."""
        header("1. Required Files")

        results = []

        # Check for config
        if Path("js/config.json").exists():
            results.append(self.check_file_exists("js/config.json", "Config"))
        else:
            fail("Config: js/config.json (not found)")
            info("Run: python setup_config.py")
            self.errors.append("Missing config: js/config.json")
            results.append(False)

        # Check for credentials
        creds_path = "credentials.json"
        if self.config:
            creds_path = self.config.get("gmail", {}).get("credentials_path", "credentials.json")

        if not Path(creds_path).exists():
            fail(f"Gmail credentials: {creds_path} (not found)")
            info("Run: python setup_gmail.py")
            self.errors.append(f"Missing Gmail credentials: {creds_path}")
            results.append(False)
        else:
            results.append(self.check_file_exists(creds_path, "Gmail credentials"))

        # Check for token (optional but recommended)
        token_path = "token.json"
        if self.config:
            token_path = self.config.get("gmail", {}).get("token_path", "token.json")

        if not Path(token_path).exists():
            warn(f"Gmail token: {token_path} (not found)")
            info("Will be created on first Gmail connection")
            self.warnings.append("Gmail token not yet created")
        else:
            ok(f"Gmail token: {token_path}")

        # Check for my_player.py
        results.append(self.check_file_exists("my_player.py", "PlayerAI module"))

        return all(results)

    def check_config(self) -> bool:
        """Check that config is valid."""
        header("2. Configuration")

        config_path = Path("js/config.json")
        if not config_path.exists():
            fail("Config file not found")
            return False

        try:
            with open(config_path) as f:
                self.config = json.load(f)
            ok("Config file is valid JSON")
        except json.JSONDecodeError as e:
            fail(f"Config file has invalid JSON: {e}")
            self.errors.append("Invalid JSON in config.json")
            return False

        # Check required sections
        required_sections = ["gmail", "database", "league", "player"]
        missing = [s for s in required_sections if s not in self.config]
        if missing:
            fail(f"Missing config sections: {', '.join(missing)}")
            self.errors.append(f"Missing config sections: {missing}")
            return False
        ok("All required config sections present")

        # Check Gmail config
        gmail = self.config.get("gmail", {})
        if not gmail.get("account"):
            fail("gmail.account is empty")
            self.errors.append("Empty gmail.account")
        elif "@" not in gmail.get("account", ""):
            fail(f"gmail.account doesn't look like an email: {gmail.get('account')}")
            self.errors.append("Invalid gmail.account")
        else:
            ok(f"Gmail account: {gmail.get('account')}")

        # Check player config
        player = self.config.get("player", {})
        if player.get("user_id"):
            ok(f"Player ID: {player.get('user_id')}")
        else:
            fail("player.user_id is empty")
            self.errors.append("Empty player.user_id")

        # Check league config
        league = self.config.get("league", {})
        if league.get("manager_email"):
            ok(f"League manager: {league.get('manager_email')}")
        else:
            fail("league.manager_email is empty")
            self.errors.append("Empty league.manager_email")

        # Check demo mode
        app = self.config.get("app", {})
        demo_mode = app.get("demo_mode", False)
        if demo_mode:
            info("Demo mode is ENABLED")
        else:
            info("Demo mode is disabled (using my_player.py)")

        return len([e for e in self.errors if "config" in e.lower()]) == 0

    def check_gmail(self) -> bool:
        """Check Gmail API connection."""
        header("3. Gmail API")

        if not self.config:
            fail("Cannot check Gmail without valid config")
            return False

        creds_path = Path(self.config.get("gmail", {}).get("credentials_path", "credentials.json"))
        token_path = Path(self.config.get("gmail", {}).get("token_path", "token.json"))

        if not creds_path.exists():
            fail(f"Credentials file not found: {creds_path}")
            return False

        if not token_path.exists():
            warn("Token file not found - Gmail not yet authenticated")
            info("Run: python setup_gmail.py")
            self.warnings.append("Gmail not yet authenticated")
            return True  # Not a fatal error

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            SCOPES = [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.modify",
            ]

            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

            if creds.expired:
                warn("Gmail token is expired")
                info("Run: python setup_gmail.py")
                self.warnings.append("Gmail token expired")
                return True

            service = build("gmail", "v1", credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            email = profile.get("emailAddress", "unknown")

            ok(f"Connected to Gmail as: {email}")

            # Verify email matches config
            config_email = self.config.get("gmail", {}).get("account", "")
            if email.lower() != config_email.lower():
                warn(f"Gmail account mismatch: config has {config_email}")
                self.warnings.append(f"Gmail account mismatch: authenticated as {email}, config has {config_email}")

            return True

        except ImportError:
            fail("Google API packages not installed")
            info("Run: pip install google-auth-oauthlib google-api-python-client")
            self.errors.append("Missing Google API packages")
            return False
        except Exception as e:
            fail(f"Gmail connection failed: {e}")
            self.errors.append(f"Gmail connection failed: {e}")
            return False

    def check_database(self) -> bool:
        """Check database connection."""
        header("4. Database")

        if not self.config:
            fail("Cannot check database without valid config")
            return False

        db_config = self.config.get("database", {})
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432)
        name = db_config.get("name", "q21_player")
        user = db_config.get("user", "postgres")

        info(f"Database: {user}@{host}:{port}/{name}")

        try:
            import psycopg2

            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=name,
                user=user,
                password=db_config.get("password", ""),
                connect_timeout=5
            )
            conn.close()
            ok("Database connection successful")
            return True

        except ImportError:
            warn("psycopg2 not installed - cannot verify database")
            info("Database check skipped (install psycopg2 to verify)")
            self.warnings.append("Cannot verify database: psycopg2 not installed")
            return True
        except Exception as e:
            fail(f"Database connection failed: {e}")
            self.errors.append(f"Database connection failed: {e}")
            return False

    def check_player_ai(self) -> bool:
        """Check that PlayerAI can be loaded."""
        header("5. PlayerAI")

        if not self.config:
            fail("Cannot check PlayerAI without valid config")
            return False

        app_config = self.config.get("app", {})
        demo_mode = app_config.get("demo_mode", False)

        if demo_mode:
            info("Demo mode enabled - using built-in DemoAI")
            ok("DemoAI will be used for game responses")
            return True

        module_name = app_config.get("player_ai_module", "my_player")
        class_name = app_config.get("player_ai_class", "MyPlayerAI")

        info(f"Loading: {module_name}.{class_name}")

        try:
            module = importlib.import_module(module_name)
            player_class = getattr(module, class_name)
            instance = player_class()

            # Check required methods
            required_methods = ["get_warmup_answer", "get_questions", "get_guess", "on_score_received"]
            missing_methods = [m for m in required_methods if not hasattr(instance, m)]

            if missing_methods:
                fail(f"Missing methods: {', '.join(missing_methods)}")
                self.errors.append(f"PlayerAI missing methods: {missing_methods}")
                return False

            ok(f"PlayerAI loaded: {class_name}")
            ok("All required methods present")
            return True

        except ImportError as e:
            fail(f"Cannot import module '{module_name}': {e}")
            self.errors.append(f"Cannot import PlayerAI module: {e}")
            return False
        except AttributeError as e:
            fail(f"Class '{class_name}' not found in module '{module_name}'")
            self.errors.append(f"PlayerAI class not found: {e}")
            return False
        except Exception as e:
            fail(f"Error loading PlayerAI: {e}")
            self.errors.append(f"PlayerAI load error: {e}")
            return False

    def run(self) -> bool:
        """Run all verification checks."""
        print("\n" + "=" * 50)
        print("  Q21 Player SDK - Setup Verification")
        print("=" * 50)

        # Load config first
        if Path("js/config.json").exists():
            try:
                with open("js/config.json") as f:
                    self.config = json.load(f)
            except:
                pass

        results = [
            self.check_required_files(),
            self.check_config(),
            self.check_gmail(),
            self.check_database(),
            self.check_player_ai(),
        ]

        # Summary
        header("Summary")

        if self.errors:
            fail(f"{len(self.errors)} error(s) found:")
            for error in self.errors:
                print(f"      - {error}")
        else:
            ok("No errors found")

        if self.warnings:
            warn(f"{len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"      - {warning}")

        if not self.errors:
            print(f"\n  {Colors.GREEN}{Colors.BOLD}Setup is complete!{Colors.RESET}")
            print("\n  You can now run:")
            print("    python run.py --scan --demo   # Test with demo mode")
            print("    python run.py --scan          # Run with your PlayerAI")
        else:
            print(f"\n  {Colors.RED}{Colors.BOLD}Setup incomplete.{Colors.RESET}")
            print("\n  Fix the errors above and run this script again.")

        print()
        return len(self.errors) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Q21 Player SDK setup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    verifier = SetupVerifier(verbose=args.verbose)
    success = verifier.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
