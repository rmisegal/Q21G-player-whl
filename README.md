# Q21 Player SDK

SDK for implementing a Q21 (21-Questions) game player that communicates with the League Manager and Referees via the unified protocol.

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/OmryTzabbar1/q21-player-sdk.git
cd q21-player-sdk
python3.11 -m venv .venv
source .venv/bin/activate
pip install dist/q21_player-1.0.0-py3-none-any.whl
```

### 2. Setup Google Cloud (Gmail API)

The SDK uses Gmail to communicate with the game server. You need OAuth credentials from Google Cloud.

#### Create OAuth Credentials (one-time setup)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. **Enable Gmail API**:
   - Go to **APIs & Services** → **Library**
   - Search for "Gmail API" → Click **Enable**
4. **Configure OAuth consent screen**:
   - Go to **APIs & Services** → **OAuth consent screen**
   - Select **External** → **Create**
   - Fill in: App name, User support email, Developer contact
   - Click through to "Test users" → Add your Gmail address
5. **Create credentials**:
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**
   - Application type: **Desktop app**
   - Click **Create** → **Download JSON**

### 3. Run Setup Wizard

```bash
python setup.py
```

This unified wizard:
1. **Gmail OAuth** - Authenticates with Google (auto-detects your email)
2. **Configuration** - Asks for player ID, league info, database settings
3. **Verification** - Confirms everything is working

The wizard will prompt for your downloaded credentials JSON when needed.

### 4. Initialize Database

```bash
python init_db.py
```

This creates all required tables in your PostgreSQL database.

### 5. Test with Demo Mode

```bash
python run.py --watch --demo
```

Demo mode uses predictable responses - no AI implementation needed yet.

### 6. Implement Your Player

Edit `my_player.py` - implement the four required methods:

- `get_warmup_answer()` - Solve a math warmup question
- `get_questions()` - Generate 20 strategic yes/no questions
- `get_guess()` - Guess the opening sentence based on answers
- `on_score_received()` - Handle score notification

### 7. Run

```bash
# Single scan - process messages once
python run.py --scan

# Continuous mode - poll for messages
python run.py --watch

# With demo mode (for testing)
python run.py --scan --demo
python run.py --watch --demo
```

## Architecture

The SDK uses a layered architecture for handling protocol messages:

```
┌─────────────────────────────────────────────────────────────┐
│                      MessageRouter                           │
│         Routes messages to RLGM or GMC based on type         │
└─────────────────────┬───────────────────────┬───────────────┘
                      │                       │
        BROADCAST_* messages           Q21* messages
                      │                       │
                      ▼                       ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│         RLGM                │   │          GMC                │
│  (League-level handling)    │   │   (Game-level handling)     │
│                             │   │                             │
│  • LeagueHandler            │   │  • Q21Handler               │
│  • RoundManager             │   │  • GameExecutor             │
│  • GPRMBuilder              │   │                             │
└─────────────────────────────┘   └─────────────────────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| **MessageRouter** | Entry point - routes messages by prefix |
| **RLGMController** | Handles league broadcasts (registration, assignments, rounds) |
| **GMController** | Manages Q21 game lifecycle |
| **LeagueHandler** | Processes BROADCAST_* messages |
| **RoundManager** | Tracks assignments and builds GPRM objects |
| **Q21Handler** | Routes Q21 messages to game phases |
| **GameExecutor** | Executes game phases via PlayerAI callbacks |

## Protocol Messages

### League Messages (league.v2)

| Message | Direction | Description |
|---------|-----------|-------------|
| `BROADCAST_START_SEASON` | LM → Player | Season announcement |
| `SEASON_REGISTRATION_REQUEST` | Player → LM | Register for season |
| `SEASON_REGISTRATION_RESPONSE` | LM → Player | Registration confirmation |
| `BROADCAST_ASSIGNMENT_TABLE` | LM → Player | All game assignments for season |
| `BROADCAST_NEW_LEAGUE_ROUND` | LM → Player | Round start signal |
| `LEAGUE_COMPLETED` | LM → Player | Season complete |

### Q21 Game Messages (Q21G.v1)

| Message | Direction | Description |
|---------|-----------|-------------|
| `Q21WARMUPCALL` | Referee → Player | Warmup question |
| `Q21WARMUPRESPONSE` | Player → Referee | Warmup answer |
| `Q21ROUNDSTART` | Referee → Player | Book info, triggers questions |
| `Q21QUESTIONSBATCH` | Player → Referee | 20 multiple-choice questions |
| `Q21ANSWERSBATCH` | Referee → Player | Answers, triggers guess |
| `Q21GUESSSUBMISSION` | Player → Referee | Final guess |
| `Q21SCOREFEEDBACK` | Referee → Player | Score breakdown (terminal) |

## Project Structure

```
q21-player-sdk/
├── setup.py                   # Unified setup wizard (start here!)
├── init_db.py                 # Database schema initialization
├── setup_gmail.py             # Gmail OAuth setup (standalone)
├── setup_config.py            # Configuration generator (standalone)
├── verify_setup.py            # Setup verification script
├── run.py                     # Entry point with --demo support
├── my_player.py               # Your PlayerAI implementation
├── _infra/                    # Protocol infrastructure
│   ├── router.py              # MessageRouter - unified entry point
│   ├── demo_ai.py             # DemoAI for testing
│   ├── rlgm/                   # League-level components
│   │   ├── controller.py      # RLGMController
│   │   ├── league_handler.py  # BROADCAST_* handlers
│   │   ├── round_manager.py   # Assignment tracking
│   │   └── gprm.py            # GPRM & GameResult dataclasses
│   └── gmc/                    # Game-level components
│       ├── controller.py      # GMController
│       ├── q21_handler.py     # Q21* message routing
│       └── game_executor.py   # PlayerAI callback execution
├── dist/
│   └── q21_player-*.whl       # SDK package
├── js/
│   ├── config.template.json   # Configuration template
│   └── config.json            # Your configuration (DO NOT COMMIT)
├── .env                       # Environment variables (DO NOT COMMIT)
├── credentials.json           # Gmail OAuth credentials (DO NOT COMMIT)
├── token.json                 # OAuth token (DO NOT COMMIT)
└── docs/
    └── prd-rlgm.md            # RLGM architecture PRD
```

## Configuration

Run `python setup_config.py` to generate configuration interactively.

Key settings in `js/config.json`:

| Section | Field | Description |
|---------|-------|-------------|
| `gmail.account` | Your Gmail address | Used for sending/receiving game messages |
| `gmail.credentials_path` | OAuth credentials file | Download from Google Cloud Console |
| `player.user_id` | Your player ID | Provided by instructor |
| `player.display_name` | Your display name | Shown in game results |
| `league.manager_email` | League Manager email | Provided by instructor |
| `database.*` | PostgreSQL settings | For storing game state |
| `app.demo_mode` | Enable demo mode | Use `true` for testing |

See `CONFIG_GUIDE.md` for detailed explanations.

## Game Flow

```
1. BROADCAST_START_SEASON
   └── Player sends SEASON_REGISTRATION_REQUEST

2. BROADCAST_ASSIGNMENT_TABLE
   └── Player stores assignments for all rounds

3. BROADCAST_NEW_LEAGUE_ROUND (per round)
   └── Player retrieves assignments, waits for referee

4. Q21 Game (per match):
   Q21WARMUPCALL ──► Q21WARMUPRESPONSE
   Q21ROUNDSTART ──► Q21QUESTIONSBATCH (auto)
   Q21ANSWERSBATCH ──► Q21GUESSSUBMISSION (auto)
   Q21SCOREFEEDBACK (terminal)

5. LEAGUE_COMPLETED
   └── Season ends
```

## Tips

- **Start with demo mode** - Run `python run.py --scan --demo` to verify your setup works before implementing your AI
- **Justifications must be 35+ words** - The `sentence_justification` and `word_justification` fields require detailed explanations
- **20 questions exactly** - `get_questions()` must return exactly 20 questions
- **Options format** - Each question needs `{"A": "...", "B": "...", "C": "...", "D": "..."}`
- **Test locally** - Use `--test-connectivity` to verify Gmail and database setup

## Demo Mode

Demo mode provides predictable responses for testing the system integration:

| Method | Demo Response |
|--------|---------------|
| `get_warmup_answer()` | Returns `{"answer": "4"}` |
| `get_questions()` | Returns 20 demo questions with A/B/C/D options |
| `get_guess()` | Returns fixed opening sentence, "demo" word, 75% confidence |
| `on_score_received()` | Prints score to console |

Enable demo mode in one of two ways:
1. **CLI flag**: `python run.py --scan --demo`
2. **Config**: Set `"demo_mode": true` in `js/config.json`

## Troubleshooting

### Gmail Authentication Errors

```bash
# Re-run Gmail setup
python setup_gmail.py

# Or delete token and re-authenticate
rm token.json
python setup_gmail.py
```

### "Credentials file not found"

Make sure you've completed the Google Cloud setup:
```bash
python setup_gmail.py --credentials /path/to/downloaded/client_secret_*.json
```

### "Access blocked: This app's request is invalid"

Your OAuth consent screen may not be configured correctly:
1. Go to Google Cloud Console → APIs & Services → OAuth consent screen
2. Make sure your Gmail is added as a test user
3. Re-download credentials and run `python setup_gmail.py` again

### Database Connection Failed

```bash
# Check PostgreSQL is running
pg_isready

# Create database if needed
createdb q21_player
```

### Verify Everything

```bash
python verify_setup.py
```

This will identify exactly what's missing or misconfigured.
