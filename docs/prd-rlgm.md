# PRD: RLGM (Referee-League Game Manager)
Version: 2.1.0

## Document Info
- **Area**: League Management
- **PRD Location**: `docs/prd-rlgm.md`
- **Comparison Doc**: `docs/comparison-gmailasplayer-vs-rlgm.md`
- **Related Modules**: `_infra/rlgm/`, `_infra/gmc/`

---

## 1. Executive Summary

The RLGM (Referee-League Game Manager) is a middleware component that sits between the League Manager and the GMC (Game Manager Component). It handles all league-level communication while delegating individual game execution to the GMC.

**Key Principle**: Students only see the 4 PlayerAI callbacks. All RLGM and GMC code is hidden infrastructure.

---

## 2. Terminology

| Term | Full Name | Description |
|------|-----------|-------------|
| **GMC** | Game Manager Component | Handles a single Q21 game cycle with the referee |
| **RLGM** | Referee-League Game Manager | Interfaces between League Manager and GMC |
| **GPRM** | Game Parameters | Input data needed to run a single game |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           STUDENT LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  my_player.py (StudentPlayerAI)                                  │    │
│  │  ├── get_warmup_answer(ctx) -> {"answer": str}                   │    │
│  │  ├── get_questions(ctx) -> {"questions": [...]}                  │    │
│  │  ├── get_guess(ctx) -> {"opening_sentence": ..., ...}            │    │
│  │  └── on_score_received(ctx) -> None                              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        HIDDEN INFRASTRUCTURE                             │
│                                                                          │
│  ┌──────────────────────┐         ┌──────────────────────┐             │
│  │      RLGM            │         │        GMC           │             │
│  │  ┌────────────────┐  │         │  ┌────────────────┐  │             │
│  │  │ RLGMController │  │ GPRM    │  │ GMController   │  │             │
│  │  └───────┬────────┘  │────────>│  └───────┬────────┘  │             │
│  │          │           │         │          │           │             │
│  │  ┌───────▼────────┐  │ Result  │  ┌───────▼────────┐  │             │
│  │  │ LeagueHandler  │  │<────────│  │ GameExecutor   │  │             │
│  │  │ Lifecycle Mgr  │  │         │  │ Q21Handler     │  │             │
│  │  │ GPRMBuilder    │  │         │  └────────────────┘  │             │
│  │  └────────────────┘  │         │                      │             │
│  └──────────┬───────────┘         └──────────┬───────────┘             │
│             │                                │                          │
└─────────────┼────────────────────────────────┼──────────────────────────┘
              │                                │
              ▼                                ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│    LEAGUE MANAGER       │      │       REFEREE           │
│    (via Gmail)          │      │       (via Gmail)       │
│                         │      │                         │
│ - BROADCAST_START_SEASON│      │ - Q21WARMUPCALL         │
│ - BROADCAST_ASSIGNMENT  │      │ - Q21ROUNDSTART         │
│ - BROADCAST_NEW_ROUND   │      │ - Q21ANSWERSBATCH       │
│ - LEAGUE_COMPLETED      │      │ - Q21SCOREFEEDBACK      │
│                         │      │                         │
└─────────────────────────┘      └─────────────────────────┘
```

---

## 4. Module Structure

```
_infra/
├── router.py                          # MessageRouter - unified entry point
├── rlgm/                              # RLGM Package
│   ├── __init__.py                    # Package exports
│   ├── controller.py                  # ~97 lines - RLGMController orchestrator
│   ├── league_handler.py              # ~228 lines - League broadcasts
│   ├── round_lifecycle.py             # ~143 lines - RoundLifecycleManager (NEW)
│   ├── termination.py                 # ~63 lines - GamePhase, TerminationReport (NEW)
│   └── gprm.py                        # ~111 lines - GPRM, GameResult, GPRMBuilder
│
├── gmc/                               # GMC Package
│   ├── __init__.py                    # Package exports
│   ├── controller.py                  # ~139 lines - GMController with phase tracking
│   ├── q21_handler.py                 # ~125 lines - Q21 message types + dispatch
│   └── game_executor.py               # ~256 lines - PlayerAI callback execution
│
└── shared/logging/                    # Protocol logging
```

---

## 5. GPRM Definition

```python
# File: _infra/rlgm/gprm.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class GPRM:
    """Game Parameters - immutable input to GMC."""
    # Identity
    match_id: str           # Same as game_id (e.g., "0102003")
    game_id: str            # 7-digit SSRRGGG format (e.g., "0102003")
    season_id: str          # e.g., "SEASON01"
    round_number: int       # Extracted from game_id[2:4]
    game_number: int        # Extracted from game_id[4:7]

    # Participants
    referee_email: str      # From assignment
    opponent_email: Optional[str]
    my_role: str            # "PLAYER1" or "PLAYER2" (per protocol)

    # Game content (populated from Q21ROUNDSTART, empty at assignment time)
    book_name: str          # Book/lecture title
    book_hint: str          # Description (15 words)
    association_word: str   # Word from association domain

    # Authentication
    auth_token: str


@dataclass
class GameResult:
    """Result returned by GMC."""
    match_id: str
    game_id: str
    status: str             # COMPLETED, FAILED, TIMEOUT
    league_points: int
    private_score: float
    breakdown: dict
    error: Optional[str] = None
```

---

## 6. Round Lifecycle Management (v2.0.0)

### 6.1 RoundLifecycleManager

Sits between RLGMController and GMController. Owns the current round, all its games, and provides atomic round transitions.

```
RLGMController
    ├── LeagueHandler           (league broadcasts)
    └── RoundLifecycleManager   (round + game ownership)
            ├── GMController [game 0101001]   ← one per game
            ├── GMController [game 0101002]
            └── GMController [game 0101003]
```

**Key Methods:**
- `start_round(N)` — Stops current round (if any), creates fresh GMControllers per assignment, returns GPRMs + termination reports
- `stop_current_round(reason)` — Force-stops all incomplete games, returns TerminationReports
- `route_q21_message(type, payload, sender)` — Routes Q21 messages to correct GMController by match_id

### 6.2 GamePhase and TerminationReport

```
GamePhase: INITIALIZED → WARMUP_COMPLETE → QUESTIONS_SENT → GUESS_SUBMITTED → COMPLETED
                                                                                 ↓
                                                                            TERMINATED
```

When a round transition force-stops an incomplete game, a `TerminationReport` captures the game state snapshot and converts to a `MATCH_RESULT_REPORT` protocol message sent to the LGM.

### 6.3 GMController Phase Tracking

Each GMController tracks:
- `phase` — Current GamePhase
- `last_sent` / `last_received` — Message history for termination reporting
- `initialize()` — Set up for a specific game
- `terminate()` — Mark as TERMINATED
- `get_termination_report(reason)` — Snapshot state

---

## 7. Message Flow

### 7.1 RLGM <-> League Manager

| Direction | Message | Handler | Response |
|-----------|---------|---------|----------|
| LM -> RLGM | `BROADCAST_START_SEASON` | `league_handler.handle_start_season()` | `SEASON_REGISTRATION_REQUEST` |
| LM -> RLGM | `SEASON_REGISTRATION_RESPONSE` | `league_handler.handle_registration_response()` | None |
| LM -> RLGM | `BROADCAST_ASSIGNMENT_TABLE` | `league_handler.handle_assignment_table()` | `GROUP_ASSIGNMENT_RESPONSE` |
| LM -> RLGM | `BROADCAST_NEW_LEAGUE_ROUND` | `lifecycle.start_round()` via controller | None (stops prev round, starts new games) |
| LM -> RLGM | `LEAGUE_COMPLETED` | `league_handler.handle_league_completed()` + `lifecycle.stop_current_round()` | None |

### 7.2 GMC <-> Referee

Message names follow Q21G.v1 protocol (no underscores).

| Direction | Message | Handler | Callback |
|-----------|---------|---------|----------|
| REF -> GMC | `Q21WARMUPCALL` | `game_executor.execute_warmup()` | `get_warmup_answer()` |
| GMC -> REF | `Q21WARMUPRESPONSE` | | |
| REF -> GMC | `Q21ROUNDSTART` | `game_executor.handle_round_start()` + `execute_questions()` | `get_questions()` |
| GMC -> REF | `Q21QUESTIONSBATCH` | | |
| REF -> GMC | `Q21ANSWERSBATCH` | `game_executor.execute_guess()` | `get_guess()` |
| GMC -> REF | `Q21GUESSSUBMISSION` | | |
| REF -> GMC | `Q21SCOREFEEDBACK` | `game_executor.handle_score()` | `on_score_received()` |

### 7.3 Score Tracking

The player tracks scores internally for:
- Knowing league standing
- Optimizing callback strategies

```python
@dataclass
class PlayerStandings:
    season_id: str
    round_number: int
    total_score: float
    games_played: int
    games_won: int
    rank: int
    history: list[RoundResult]
```

---

## 8. Historical Notes

> Sections 8-10 from PRD v1.x documented initial planning (code isolation,
> implementation phases, gap fixes). All phases are **completed** as of v2.0.0.
> See git history for the original planning content.
>
> **Key gaps resolved:**
> - Gap #1 (`on_score_received()` not called) — Fixed in `gmc/game_executor.py`
> - Gap #2 (`LEAGUE_COMPLETED` not handled) — Fixed in `rlgm/league_handler.py`
> - Gap #3 (Logging context for game_id) — Fixed in v1.1.0 via `set_game_context()`
> - Gap #4 (game_id format per message type) — Fixed in v1.3.0 with three context levels

---

## 9. Success Criteria

1. All League Manager broadcasts handled by RLGM
2. All Q21 messages handled by GMC
3. GPRM correctly populated from assignments
4. GMC returns GameResult to RLGM
5. All 4 PlayerAI callbacks invoked correctly
6. No functionality gaps vs GmailAsPlayer
7. Students only see PlayerAI interface
8. All files under 150 lines
9. No hardcoded values
10. Player score tracking for optimization
11. TDD approach with tests first
