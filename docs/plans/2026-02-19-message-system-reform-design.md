# Message System Reform — Round Lifecycle Management
Version: 1.0.0

## IMPORTANT: Development Practices

Before implementing this design, read `CLAUDE.md` and follow ALL development practices:
- **TDD** — Write tests first, then implement to make them pass
- **150-line file limit** — All Python files must stay under 150 lines
- **Code-to-PRD mapping** — Every source file needs Area/PRD header comments
- **Sync requirement** — Update `docs/prd-rlgm.md` when modifying RLGM/GMC code (increment version, match implementation)
- **No hardcoded values** — All config from `config.json` or environment variables
- **Modularity** — Small, focused modules with clear responsibilities
- **Check existing code first** — Search codebase before implementing anything new

---

## Problem Statement

The current message handling system has no round lifecycle management:

1. **No round transitions** — When `BROADCAST_NEW_LEAGUE_ROUND` arrives, nothing stops games from the prior round. The handler just sets a counter and returns GPRM objects.
2. **Single-game GMController** — `GMController` tracks one game via a flat `_game_state` dict. Multiple games per round overwrite each other.
3. **No game state tracking** — No concept of game phases (warmup, questions, guess). No record of what was sent/received. No way to report game status on termination.
4. **Fire-and-forget routing** — Q21 messages go to a single `GMController` with no match_id-based dispatch.

These gaps block both the malfunction detection system (needs to know game state) and the gatekeeper (needs round-scoped message filtering).

---

## Architecture

### New Component: RoundLifecycleManager

Sits between `RLGMController` and `GMController`. Owns the current round, all its games, and provides atomic round transitions.

```
RLGMController
    ├── LeagueHandler           (unchanged — registration, assignments)
    └── RoundLifecycleManager   (NEW — replaces RoundManager + single GMController)
            ├── GMController [game 0101001]   ← one per game
            ├── GMController [game 0101002]
            └── GMController [game 0101003]
```

### Message Flow

#### Inbound: League Messages

```
MessageRouter.route_message(msg_type, payload, sender)
    └── RLGMController.process_message()
            ├── BROADCAST_START_SEASON      → LeagueHandler (unchanged)
            ├── SEASON_REGISTRATION_RESPONSE → LeagueHandler (unchanged)
            ├── BROADCAST_ASSIGNMENT_TABLE   → LeagueHandler + store assignments
            ├── BROADCAST_NEW_LEAGUE_ROUND   → NEW FLOW:
            │       1. lifecycle.stop_current_round()
            │          → captures state of each active game
            │          → returns List[TerminationReport] for incomplete games
            │       2. lifecycle.start_round(N, assignments)
            │          → creates fresh GMController per game
            │          → returns List[GPRM]
            │       3. Return RoutingResult with termination_reports
            │          → caller sends MATCH_RESULT_REPORT emails to LGM
            └── LEAGUE_COMPLETED            → LeagueHandler + lifecycle.stop_current_round()
```

#### Inbound: Q21 Game Messages

```
MessageRouter.route_message(msg_type, payload, sender)
    └── RLGMController.process_q21_message()
            └── lifecycle.route_q21_message(msg_type, payload, sender)
                    ├── Extract match_id from payload
                    ├── Lookup GMController in active_games[match_id]
                    │   (if not found → log warning, return None — stale message)
                    └── controller.handle_q21_message(msg_type, payload, sender)
                            → returns Q21Response
```

---

## Components

### 1. RoundLifecycleManager

**File:** `_infra/rlgm/round_lifecycle.py`
**Responsibility:** Owns current round and all its games. Atomic round transitions.

```python
class RoundLifecycleManager:
    # State
    current_round: int
    season_id: str
    active_games: dict[str, GMController]  # match_id → controller
    _player_ai: PlayerAIProtocol
    _assignments: dict[int, list]          # round_number → assignment list

    # Round transitions
    def start_round(self, round_number: int, assignments: List[dict]) -> List[GPRM]:
        """Stop current round (if any), create new GMControllers, return GPRMs."""

    def stop_current_round(self, reason: str = "NEW_ROUND_STARTED") -> List[TerminationReport]:
        """Force-stop all active games, return termination reports for incomplete ones."""

    # Message routing
    def route_q21_message(self, msg_type: str, payload: dict, sender: str) -> Optional[dict]:
        """Route Q21 message to correct GMController by match_id."""

    # Assignment storage (subsumed from RoundManager)
    def set_assignments(self, round_number: int, assignments: List[dict]) -> None:
        """Store assignments for a round."""

    # Queries
    def get_game(self, match_id: str) -> Optional[GMController]:
    def get_active_match_ids(self) -> List[str]:
    def is_round_complete(self) -> bool:
```

#### `stop_current_round()` Algorithm

```
For each (match_id, controller) in active_games:
    if controller.phase == COMPLETED:
        skip (already done)
    else:
        report = controller.get_termination_report(reason)
        reports.append(report)
        controller.terminate()
Clear active_games
Return reports
```

#### `start_round()` Algorithm

```
1. If active_games not empty → call stop_current_round()
2. Set current_round = round_number
3. For each assignment in assignments_for_round:
       gmc = GMController(player_ai=self._player_ai)
       gmc.initialize(match_id, game_id, referee_email, ...)
       active_games[match_id] = gmc
4. Return list of GPRM objects
```

#### `route_q21_message()` Algorithm

```
1. match_id = payload.get("match_id", "")
2. controller = active_games.get(match_id)
3. If controller is None:
       log warning: "Q21 message for unknown match_id {match_id} — stale message?"
       return None
4. response = controller.handle_q21_message(msg_type, payload, sender)
5. Return formatted response dict
```

---

### 2. TerminationReport and GamePhase

**File:** `_infra/rlgm/termination.py`

```python
class GamePhase(Enum):
    INITIALIZED = "INITIALIZED"
    WARMUP_COMPLETE = "WARMUP_COMPLETE"
    QUESTIONS_SENT = "QUESTIONS_SENT"
    GUESS_SUBMITTED = "GUESS_SUBMITTED"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"

@dataclass
class TerminationReport:
    match_id: str
    game_id: str
    round_number: int
    season_id: str
    phase_at_termination: str
    last_actor: str             # "PLAYER", "REFEREE", or "NONE"
    last_message_sent: str      # Last msg type player sent
    last_message_received: str  # Last msg type player received
    terminated_at: str          # ISO timestamp
    reason: str                 # "NEW_ROUND_STARTED" or "LEAGUE_COMPLETED"
```

#### Phase → Last Actor Mapping

| Phase | Player Last Sent | Waiting For | last_actor |
|-------|-----------------|-------------|------------|
| INITIALIZED | — | Q21WARMUPCALL | NONE |
| WARMUP_COMPLETE | Q21WARMUPRESPONSE | Q21ROUNDSTART | PLAYER |
| QUESTIONS_SENT | Q21QUESTIONSBATCH | Q21ANSWERSBATCH | PLAYER |
| GUESS_SUBMITTED | Q21GUESSSUBMISSION | Q21SCOREFEEDBACK | PLAYER |
| COMPLETED | — | — | N/A |

---

### 3. GMController Changes

**File:** `_infra/gmc/controller.py` (modified)

Replace the flat `_game_state` dict with explicit phase and message tracking:

```python
class GMController:
    _phase: GamePhase
    _match_id: str
    _game_id: str
    _round_number: int
    _season_id: str
    _referee_email: str
    _last_sent: Optional[str]
    _last_received: Optional[str]
    _executor: GameExecutor

    def initialize(self, match_id, game_id, round_number, season_id, referee_email):
        """Set up controller for a specific game."""

    def handle_q21_message(self, msg_type, payload, sender) -> Optional[Q21Response]:
        """Handle Q21 message. Updates _phase, _last_sent, _last_received."""

    def get_termination_report(self, reason: str) -> TerminationReport:
        """Snapshot current state for termination reporting."""

    def terminate(self) -> None:
        """Mark game as TERMINATED."""

    @property
    def phase(self) -> GamePhase:
        """Current game phase."""
```

#### handle_q21_message() Phase Transitions

```
Q21WARMUPCALL    → _last_received = "Q21WARMUPCALL"
                    execute warmup
                    _last_sent = "Q21WARMUPRESPONSE"
                    _phase = WARMUP_COMPLETE

Q21ROUNDSTART    → _last_received = "Q21ROUNDSTART"
                    execute questions
                    _last_sent = "Q21QUESTIONSBATCH"
                    _phase = QUESTIONS_SENT

Q21ANSWERSBATCH  → _last_received = "Q21ANSWERSBATCH"
                    execute guess
                    _last_sent = "Q21GUESSSUBMISSION"
                    _phase = GUESS_SUBMITTED

Q21SCOREFEEDBACK → _last_received = "Q21SCOREFEEDBACK"
                    handle score
                    _phase = COMPLETED
```

---

### 4. RLGMController Changes

**File:** `_infra/rlgm/controller.py` (modified)

```python
class RLGMController:
    def __init__(self, player_email, player_name, player_ai):
        self._league_handler = LeagueHandler(player_email, player_name)
        self._lifecycle = RoundLifecycleManager(player_ai=player_ai)  # REPLACES _round_manager + _gmc
        ...

    def process_message(self, msg_type, payload, sender):
        ...
        elif msg_type == LeagueHandler.NEW_ROUND:
            round_number = payload.get("round_number", 1)
            # NEW: Stop current round, get termination reports
            reports = self._lifecycle.stop_current_round("NEW_ROUND_STARTED")
            # NEW: Start new round with assignments
            games = self._lifecycle.start_round(round_number, ...)
            return response, games, reports  # expanded return

    def process_q21_message(self, msg_type, payload, sender):
        # NEW: Route through lifecycle manager
        return self._lifecycle.route_q21_message(msg_type, payload, sender)
```

---

### 5. RoutingResult Changes

**File:** `_infra/router.py` (modified)

```python
@dataclass
class RoutingResult:
    response: Optional[dict]
    games_to_run: List[GPRM]
    handled: bool
    termination_reports: List[dict] = field(default_factory=list)  # NEW
```

---

### 6. MATCH_RESULT_REPORT Protocol Message

Sent to LGM for each incomplete game when a round is force-stopped:

```json
{
    "message_type": "MATCH_RESULT_REPORT",
    "version": "1.0",
    "match_id": "0102003",
    "game_id": "0102003",
    "round_number": 2,
    "season_id": "S01",
    "status": "TERMINATED",
    "phase_at_termination": "QUESTIONS_SENT",
    "last_actor": "PLAYER",
    "last_message_sent": "Q21QUESTIONSBATCH",
    "last_message_received": "Q21ROUNDSTART",
    "terminated_at": "2026-02-19T10:30:00Z",
    "reason": "NEW_ROUND_STARTED",
    "reporter": {
        "email": "user0009@gtai-tech.org",
        "role": "PLAYER_A"
    }
}
```

---

## File Changes Summary

### New Files (2)

| File | Lines (est.) | Content |
|------|-------------|---------|
| `_infra/rlgm/round_lifecycle.py` | ~120 | RoundLifecycleManager |
| `_infra/rlgm/termination.py` | ~40 | TerminationReport, GamePhase |

### Modified Files (2)

| File | Changes |
|------|---------|
| `_infra/rlgm/controller.py` | Replace `_round_manager` + `_gmc` with `_lifecycle`. Update `process_message()` and `process_q21_message()`. |
| `_infra/gmc/controller.py` | Replace `_game_state` dict with explicit `GamePhase`, message tracking, and `get_termination_report()`. Add `initialize()` and `terminate()`. |

### Modified Supporting Files (1)

| File | Changes |
|------|---------|
| `_infra/router.py` | Add `termination_reports` field to `RoutingResult` |

### Removed Files (1)

| File | Reason |
|------|--------|
| `_infra/rlgm/round_manager.py` | Subsumed by `round_lifecycle.py` |

### Documentation Updates Required

| Doc | Update |
|-----|--------|
| `docs/prd-rlgm.md` | Increment version. Add RoundLifecycleManager section. Update architecture diagram. Document round transition flow and MATCH_RESULT_REPORT. |
| `CLAUDE.md` | Add round_lifecycle.py and termination.py to project structure. Update Feature PRDs table if needed. |

---

## Testing Strategy

### Unit Tests

1. **RoundLifecycleManager**
   - `test_start_round_creates_controllers` — verify one GMController per assignment
   - `test_stop_current_round_returns_reports` — verify termination reports for incomplete games
   - `test_stop_skips_completed_games` — completed games produce no report
   - `test_start_round_stops_previous` — starting round N+1 auto-stops round N
   - `test_route_q21_by_match_id` — message dispatched to correct controller
   - `test_route_unknown_match_id` — returns None for stale messages

2. **GMController (modified)**
   - `test_phase_transitions` — verify INITIALIZED → WARMUP_COMPLETE → QUESTIONS_SENT → GUESS_SUBMITTED → COMPLETED
   - `test_last_sent_last_received_tracking` — verify message history
   - `test_get_termination_report` — verify correct phase, last_actor, message types
   - `test_terminate_sets_phase` — verify TERMINATED phase

3. **TerminationReport**
   - `test_phase_to_last_actor_mapping` — verify all phase→actor mappings
   - `test_to_match_result_report` — verify protocol message format

### Integration Tests

4. **Round transition flow**
   - `test_new_round_stops_and_starts` — full BROADCAST_NEW_LEAGUE_ROUND flow
   - `test_q21_message_after_round_change` — stale messages from old round are dropped
   - `test_multiple_concurrent_games` — verify independent game state per controller

---

## Future: Gatekeeper Integration Point

This design creates a clean foundation for the gatekeeper (deferred to a later session):

- **Gatekeeper wraps MessageRouter** — sits in front and handles sender validation, lookup table routing
- **RoundLifecycleManager provides game state** — gatekeeper can query `lifecycle.get_active_match_ids()` to validate incoming Q21 messages
- **Termination reports feed malfunction detection** — `MATCH_RESULT_REPORT` gives the LGM data to evaluate who was non-responsive
- **Lookup table updates** in `BROADCAST_NEW_LEAGUE_ROUND` will be parsed by the gatekeeper, which processes the payload before passing it to `RLGMController`

---

## Implementation Sessions

Recommended session split:

1. **Session 1:** `termination.py` + `GMController` changes (phase tracking, termination reports) + unit tests
2. **Session 2:** `round_lifecycle.py` + `RLGMController` changes + `RoutingResult` changes + unit tests
3. **Session 3:** Integration tests + PRD updates + README updates
