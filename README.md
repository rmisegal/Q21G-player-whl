# Q21 Player SDK

Template project for implementing a Q21 (21-Questions) game player.

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/OmryTzabbar1/q21-player-sdk.git
cd q21-player-sdk
python3.11 -m venv .venv
source .venv/bin/activate
pip install q21-player
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

## Project Structure

```
q21-player-sdk/
├── js/
│   └── config.json       # Your configuration
├── my_player.py          # Your PlayerAI implementation
├── credentials.json      # Gmail OAuth credentials (DO NOT COMMIT)
├── token.json            # OAuth token (created on first run, DO NOT COMMIT)
├── CONFIG_GUIDE.md       # Detailed config documentation
└── README.md             # This file
```

## Configuration

See `CONFIG_GUIDE.md` for detailed explanations of each config field.

Key settings in `js/config.json`:
- `gmail.account` - Your Gmail address
- `gmail.credentials_path` - Path to OAuth credentials
- `player.user_id` - Your unique player ID
- `league.manager_email` - Referee's email (from instructor)

## Tips

- **Justifications must be 35+ words** - The `sentence_justification` and `word_justification` fields require detailed explanations
- **20 questions exactly** - `get_questions()` must return exactly 20 questions
- **Options format** - Each question needs `{"A": "...", "B": "...", "C": "...", "D": "..."}`
- **Test locally** - Use `--test-connectivity` to verify Gmail and database setup
