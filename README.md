# Q21 Player SDK

SDK for implementing a Q21 (21-Questions) game player that communicates with the League Manager and Referees via the unified protocol.

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/OmryTzabbar1/q21-player-sdk.git
cd q21-player-sdk
python3.11 -m venv .venv
source .venv/bin/activate
pip install dist/q21_player-1.0.0-py3-none-any.whl
```

### 2. Configure

1. Copy your `credentials.json` from Google Cloud Console to this folder
2. Edit `js/config.json` with your settings (see `CONFIG_GUIDE.md`)

### 3. Implement Your Player

Edit `my_player.py` - implement the four required methods:

- `get_warmup_answer()` - Solve a math warmup question
- `get_questions()` - Generate 20 strategic yes/no questions
- `get_guess()` - Guess the opening sentence based on answers
- `on_score_received()` - Handle score notification

### 4. Run

```bash
# Single scan (process messages once)
q21-player --scan

# Continuous mode (poll for messages)
q21-player --watch

# Test connectivity first
q21-player --test-connectivity
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
├── _infra/                    # Protocol infrastructure
│   ├── router.py              # MessageRouter - unified entry point
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
│   └── config.json            # Your configuration
├── my_player.py               # Your PlayerAI implementation
├── credentials.json           # Gmail OAuth credentials (DO NOT COMMIT)
├── token.json                 # OAuth token (DO NOT COMMIT)
└── docs/
    └── prd-rlgm.md            # RLGM architecture PRD
```

## Configuration

See `CONFIG_GUIDE.md` for detailed explanations of each config field.

Key settings in `js/config.json`:
- `gmail.account` - Your Gmail address
- `gmail.credentials_path` - Path to OAuth credentials
- `player.user_id` - Your unique player ID
- `league.manager_email` - League Manager's email

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

- **Justifications must be 35+ words** - The `sentence_justification` and `word_justification` fields require detailed explanations
- **20 questions exactly** - `get_questions()` must return exactly 20 questions
- **Options format** - Each question needs `{"A": "...", "B": "...", "C": "...", "D": "..."}`
- **Test locally** - Use `--test-connectivity` to verify Gmail and database setup
