# Message System Reform — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken round handling with a RoundLifecycleManager that provides atomic round transitions, per-game GMControllers, and termination reporting.

**Architecture:** RoundLifecycleManager sits between RLGMController and GMController. It owns the current round's games, creates one GMController per game, and on round transition force-stops incomplete games with a MATCH_RESULT_REPORT. Q21 messages route to the correct controller by match_id.

**Tech Stack:** Python 3.11, dataclasses, enums, pytest

**Design Doc:** `docs/plans/2026-02-19-message-system-reform-design.md`

**IMPORTANT:** Read `CLAUDE.md` before implementing. Follow: TDD, 150-line file limit, Area/PRD headers, PRD sync, no hardcoded values.

---

## Task 1: Create GamePhase enum and TerminationReport dataclass

**Files:**
- Create: `_infra/rlgm/termination.py`
- Test: `tests/test_termination.py`

**Step 1: Write the failing tests**

```python
# tests/test_termination.py
"""Tests for GamePhase and TerminationReport."""
import pytest
from _infra.rlgm.termination import GamePhase, TerminationReport


class TestGamePhase:
    def test_all_phases_exist(self):
        assert GamePhase.INITIALIZED.value == "INITIALIZED"
        assert GamePhase.WARMUP_COMPLETE.value == "WARMUP_COMPLETE"
        assert GamePhase.QUESTIONS_SENT.value == "QUESTIONS_SENT"
        assert GamePhase.GUESS_SUBMITTED.value == "GUESS_SUBMITTED"
        assert GamePhase.COMPLETED.value == "COMPLETED"
        assert GamePhase.TERMINATED.value == "TERMINATED"

    def test_is_terminal(self):
        assert GamePhase.COMPLETED.value in ("COMPLETED", "TERMINATED")
        assert GamePhase.TERMINATED.value in ("COMPLETED", "TERMINATED")
        assert GamePhase.INITIALIZED.value not in ("COMPLETED", "TERMINATED")


class TestTerminationReport:
    def test_create_report(self):
        report = TerminationReport(
            match_id="0102001",
            game_id="0102001",
            round_number=2,
            season_id="S01",
            phase_at_termination="QUESTIONS_SENT",
            last_actor="PLAYER",
            last_message_sent="Q21QUESTIONSBATCH",
            last_message_received="Q21ROUNDSTART",
            terminated_at="2026-02-19T10:30:00Z",
            reason="NEW_ROUND_STARTED",
        )
        assert report.match_id == "0102001"
        assert report.last_actor == "PLAYER"

    def test_to_match_result_report(self):
        report = TerminationReport(
            match_id="0102001",
            game_id="0102001",
            round_number=2,
            season_id="S01",
            phase_at_termination="QUESTIONS_SENT",
            last_actor="PLAYER",
            last_message_sent="Q21QUESTIONSBATCH",
            last_message_received="Q21ROUNDSTART",
            terminated_at="2026-02-19T10:30:00Z",
            reason="NEW_ROUND_STARTED",
        )
        msg = report.to_protocol_message(
            reporter_email="user0009@gtai-tech.org",
            reporter_role="PLAYER_A",
        )
        assert msg["message_type"] == "MATCH_RESULT_REPORT"
        assert msg["version"] == "1.0"
        assert msg["match_id"] == "0102001"
        assert msg["status"] == "TERMINATED"
        assert msg["phase_at_termination"] == "QUESTIONS_SENT"
        assert msg["last_actor"] == "PLAYER"
        assert msg["reporter"]["email"] == "user0009@gtai-tech.org"
        assert msg["reporter"]["role"] == "PLAYER_A"

    def test_last_actor_mapping_initialized(self):
        """INITIALIZED phase: nobody acted yet."""
        report = TerminationReport(
            match_id="X", game_id="X", round_number=1, season_id="S01",
            phase_at_termination="INITIALIZED",
            last_actor="NONE",
            last_message_sent="", last_message_received="",
            terminated_at="T", reason="R",
        )
        assert report.last_actor == "NONE"

    def test_last_actor_mapping_warmup_complete(self):
        """WARMUP_COMPLETE: player sent warmup response, waiting for referee."""
        report = TerminationReport(
            match_id="X", game_id="X", round_number=1, season_id="S01",
            phase_at_termination="WARMUP_COMPLETE",
            last_actor="PLAYER",
            last_message_sent="Q21WARMUPRESPONSE",
            last_message_received="Q21WARMUPCALL",
            terminated_at="T", reason="R",
        )
        assert report.last_actor == "PLAYER"
        assert report.last_message_sent == "Q21WARMUPRESPONSE"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_termination.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_infra.rlgm.termination'`

**Step 3: Write the implementation**

```python
# _infra/rlgm/termination.py
# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Game phase tracking and termination reporting.

Provides GamePhase enum for explicit phase tracking in GMController,
and TerminationReport for capturing game state on force-stop.
"""
from dataclasses import dataclass
from enum import Enum


class GamePhase(Enum):
    """Phases of a Q21 game lifecycle."""
    INITIALIZED = "INITIALIZED"
    WARMUP_COMPLETE = "WARMUP_COMPLETE"
    QUESTIONS_SENT = "QUESTIONS_SENT"
    GUESS_SUBMITTED = "GUESS_SUBMITTED"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


@dataclass
class TerminationReport:
    """Snapshot of game state at forced termination.

    Created when a round transition force-stops an incomplete game.
    Used to generate MATCH_RESULT_REPORT protocol messages to LGM.
    """
    match_id: str
    game_id: str
    round_number: int
    season_id: str
    phase_at_termination: str
    last_actor: str              # "PLAYER", "REFEREE", or "NONE"
    last_message_sent: str       # Last msg type player sent
    last_message_received: str   # Last msg type player received
    terminated_at: str           # ISO timestamp
    reason: str                  # "NEW_ROUND_STARTED" or "LEAGUE_COMPLETED"

    def to_protocol_message(
        self, reporter_email: str, reporter_role: str
    ) -> dict:
        """Convert to MATCH_RESULT_REPORT protocol message."""
        return {
            "message_type": "MATCH_RESULT_REPORT",
            "version": "1.0",
            "match_id": self.match_id,
            "game_id": self.game_id,
            "round_number": self.round_number,
            "season_id": self.season_id,
            "status": "TERMINATED",
            "phase_at_termination": self.phase_at_termination,
            "last_actor": self.last_actor,
            "last_message_sent": self.last_message_sent,
            "last_message_received": self.last_message_received,
            "terminated_at": self.terminated_at,
            "reason": self.reason,
            "reporter": {
                "email": reporter_email,
                "role": reporter_role,
            },
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_termination.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add _infra/rlgm/termination.py tests/test_termination.py
git commit -m "feat: add GamePhase enum and TerminationReport dataclass"
```

---

## Task 2: Modify GMController — explicit phase tracking and termination reports

**Files:**
- Modify: `_infra/gmc/controller.py` (full rewrite, 154→~140 lines)
- Test: `tests/test_gmc_controller.py`

**Step 1: Write the failing tests**

```python
# tests/test_gmc_controller.py
"""Tests for GMController phase tracking and termination reports."""
import pytest
from unittest.mock import MagicMock
from _infra.gmc.controller import GMController
from _infra.gmc.q21_handler import Q21Handler
from _infra.rlgm.termination import GamePhase


def _make_mock_ai():
    """Create a mock PlayerAI that returns valid responses."""
    ai = MagicMock()
    ai.get_warmup_answer.return_value = {"answer": "42"}
    ai.get_questions.return_value = {"questions": [{"q": "test"}]}
    ai.get_guess.return_value = {
        "opening_sentence": "It was a dark night.",
        "sentence_justification": "x " * 35,
        "associative_word": "darkness",
        "word_justification": "x " * 35,
        "confidence": 0.8,
    }
    ai.on_score_received.return_value = None
    return ai


class TestGMControllerPhases:
    def test_initial_phase_is_initialized(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        assert gmc.phase == GamePhase.INITIALIZED

    def test_warmup_transitions_to_warmup_complete(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.WARMUP_COMPLETE

    def test_round_start_transitions_to_questions_sent(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.ROUND_START,
            {"match_id": "M001", "book_name": "Test", "book_hint": "hint", "association_word": "color"},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.QUESTIONS_SENT

    def test_answers_transitions_to_guess_submitted(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.ANSWERS_BATCH,
            {"match_id": "M001", "answers": [{"question_number": 1, "answer": "A"}]},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.GUESS_SUBMITTED

    def test_score_transitions_to_completed(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        result = gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": "M001", "league_points": 85, "private_score": 0.9, "breakdown": {}},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.COMPLETED
        assert result is None  # Score feedback is terminal


class TestGMControllerMessageTracking:
    def test_last_sent_after_warmup(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert gmc.last_sent == Q21Handler.WARMUP_RESPONSE
        assert gmc.last_received == Q21Handler.WARMUP_CALL

    def test_last_sent_after_questions(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.ROUND_START,
            {"match_id": "M001", "book_name": "T", "book_hint": "h", "association_word": "w"},
            "ref@test.com",
        )
        assert gmc.last_sent == Q21Handler.QUESTIONS_BATCH
        assert gmc.last_received == Q21Handler.ROUND_START


class TestGMControllerTermination:
    def test_get_termination_report(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        report = gmc.get_termination_report("NEW_ROUND_STARTED")
        assert report.match_id == "M001"
        assert report.game_id == "0102001"
        assert report.round_number == 2
        assert report.season_id == "S01"
        assert report.phase_at_termination == "WARMUP_COMPLETE"
        assert report.last_actor == "PLAYER"
        assert report.last_message_sent == Q21Handler.WARMUP_RESPONSE
        assert report.last_message_received == Q21Handler.WARMUP_CALL
        assert report.reason == "NEW_ROUND_STARTED"

    def test_terminate_sets_phase(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.terminate()
        assert gmc.phase == GamePhase.TERMINATED

    def test_termination_report_initialized_phase(self):
        """INITIALIZED: last_actor is NONE (nobody acted yet)."""
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        report = gmc.get_termination_report("NEW_ROUND_STARTED")
        assert report.last_actor == "NONE"
        assert report.last_message_sent == ""
        assert report.last_message_received == ""
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_gmc_controller.py -v`
Expected: FAIL — `GMController` has no `initialize()` method

**Step 3: Rewrite GMController**

Replace the entire contents of `_infra/gmc/controller.py` with:

```python
# Area: GMC (Game Manager Component)
# PRD: docs/prd-rlgm.md
"""GMC Controller - Game lifecycle orchestrator.

Manages the full lifecycle of a single Q21 game match.
Tracks explicit game phases and message history for termination reporting.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from _infra.gmc.game_executor import GameExecutor, PlayerAIProtocol
from _infra.gmc.q21_handler import Q21Handler, Q21Response
from _infra.rlgm.termination import GamePhase, TerminationReport

# Phase → last_actor mapping (who acted last at this phase)
_PHASE_LAST_ACTOR = {
    GamePhase.INITIALIZED: "NONE",
    GamePhase.WARMUP_COMPLETE: "PLAYER",
    GamePhase.QUESTIONS_SENT: "PLAYER",
    GamePhase.GUESS_SUBMITTED: "PLAYER",
    GamePhase.COMPLETED: "NONE",
    GamePhase.TERMINATED: "NONE",
}


class GMController:
    """Orchestrates a single Q21 game lifecycle.

    One instance per game. Tracks phase, message history, and supports
    termination reporting for round transitions.
    """

    def __init__(self, player_ai: Optional[PlayerAIProtocol] = None) -> None:
        self._executor = GameExecutor(player_ai=player_ai)
        self._phase = GamePhase.INITIALIZED
        self._match_id = ""
        self._game_id = ""
        self._round_number = 0
        self._season_id = ""
        self._referee_email = ""
        self._last_sent: Optional[str] = None
        self._last_received: Optional[str] = None

    def initialize(
        self,
        match_id: str,
        game_id: str,
        round_number: int,
        season_id: str,
        referee_email: str,
    ) -> None:
        """Set up controller for a specific game."""
        self._match_id = match_id
        self._game_id = game_id
        self._round_number = round_number
        self._season_id = season_id
        self._referee_email = referee_email
        self._phase = GamePhase.INITIALIZED

    @property
    def phase(self) -> GamePhase:
        return self._phase

    @property
    def last_sent(self) -> Optional[str]:
        return self._last_sent

    @property
    def last_received(self) -> Optional[str]:
        return self._last_received

    @property
    def match_id(self) -> str:
        return self._match_id

    def handle_q21_message(
        self, msg_type: str, payload: dict[str, Any], sender: str
    ) -> Optional[Q21Response]:
        """Handle Q21 message. Updates phase and message history."""
        match_id = payload.get("match_id", "")

        if msg_type == Q21Handler.WARMUP_CALL:
            self._last_received = Q21Handler.WARMUP_CALL
            result = self._executor.execute_warmup(payload)
            self._last_sent = Q21Handler.WARMUP_RESPONSE
            self._phase = GamePhase.WARMUP_COMPLETE
            return Q21Response(
                message_type=Q21Handler.WARMUP_RESPONSE,
                payload={"match_id": match_id, "answer": result["warmup_answer"]},
                recipient=sender,
            )

        elif msg_type == Q21Handler.ROUND_START:
            self._last_received = Q21Handler.ROUND_START
            self._executor.handle_round_start(payload)
            questions_result = self._executor.execute_questions(payload)
            self._last_sent = Q21Handler.QUESTIONS_BATCH
            self._phase = GamePhase.QUESTIONS_SENT
            return Q21Response(
                message_type=Q21Handler.QUESTIONS_BATCH,
                payload={"match_id": match_id, "questions": questions_result["questions"]},
                recipient=sender,
            )

        elif msg_type == Q21Handler.ANSWERS_BATCH:
            self._last_received = Q21Handler.ANSWERS_BATCH
            result = self._executor.receive_answers(payload)
            guess_payload = {**payload, "answers": result["answers"]}
            guess_result = self._executor.execute_guess(guess_payload)
            self._last_sent = Q21Handler.GUESS_SUBMISSION
            self._phase = GamePhase.GUESS_SUBMITTED
            return Q21Response(
                message_type=Q21Handler.GUESS_SUBMISSION,
                payload={"match_id": match_id, "guess": guess_result["guess"]},
                recipient=sender,
            )

        elif msg_type == Q21Handler.SCORE_FEEDBACK:
            self._last_received = Q21Handler.SCORE_FEEDBACK
            self._executor.handle_score(payload)
            self._phase = GamePhase.COMPLETED
            return None

        else:
            raise ValueError(f"Unknown Q21 message type: {msg_type}")

    def get_termination_report(self, reason: str) -> TerminationReport:
        """Snapshot current state for termination reporting."""
        return TerminationReport(
            match_id=self._match_id,
            game_id=self._game_id,
            round_number=self._round_number,
            season_id=self._season_id,
            phase_at_termination=self._phase.value,
            last_actor=_PHASE_LAST_ACTOR.get(self._phase, "NONE"),
            last_message_sent=self._last_sent or "",
            last_message_received=self._last_received or "",
            terminated_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )

    def terminate(self) -> None:
        """Mark game as TERMINATED."""
        self._phase = GamePhase.TERMINATED
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_gmc_controller.py -v`
Expected: All 10 tests PASS

**Step 5: Verify file stays under 150 lines**

Run: `wc -l _infra/gmc/controller.py`
Expected: ~130 lines (under 150 limit)

**Step 6: Commit**

```bash
git add _infra/gmc/controller.py tests/test_gmc_controller.py
git commit -m "feat: add explicit phase tracking and termination reports to GMController"
```

---

## Task 3: Create RoundLifecycleManager

**Files:**
- Create: `_infra/rlgm/round_lifecycle.py`
- Test: `tests/test_round_lifecycle.py`

**Step 1: Write the failing tests**

```python
# tests/test_round_lifecycle.py
"""Tests for RoundLifecycleManager."""
import pytest
from unittest.mock import MagicMock
from _infra.rlgm.round_lifecycle import RoundLifecycleManager
from _infra.rlgm.termination import GamePhase
from _infra.gmc.q21_handler import Q21Handler


def _make_mock_ai():
    ai = MagicMock()
    ai.get_warmup_answer.return_value = {"answer": "42"}
    ai.get_questions.return_value = {"questions": [{"q": "test"}]}
    ai.get_guess.return_value = {
        "opening_sentence": "It was dark.",
        "sentence_justification": "x " * 35,
        "associative_word": "dark",
        "word_justification": "x " * 35,
        "confidence": 0.8,
    }
    ai.on_score_received.return_value = None
    return ai


def _make_assignments(round_number, count=2):
    """Create test assignments for a round."""
    return [
        {
            "game_id": f"01{round_number:02d}{i+1:03d}",
            "match_id": f"01{round_number:02d}{i+1:03d}",
            "round_number": round_number,
            "referee_email": f"ref{i+1}@test.com",
            "opponent_email": f"opp{i+1}@test.com",
            "my_role": "PLAYER1",
            "group_id": f"G{i+1}",
        }
        for i in range(count)
    ]


class TestStartRound:
    def test_start_round_creates_controllers(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        assignments = _make_assignments(1, count=3)
        lm.set_assignments(1, assignments)
        lm.start_round(1)
        assert len(lm.get_active_match_ids()) == 3
        assert lm.current_round == 1

    def test_start_round_with_no_assignments(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.start_round(1)
        assert len(lm.get_active_match_ids()) == 0

    def test_get_game_returns_controller(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        gmc = lm.get_game(match_id)
        assert gmc is not None
        assert gmc.phase == GamePhase.INITIALIZED

    def test_get_game_unknown_returns_none(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        assert lm.get_game("NONEXISTENT") is None


class TestStopRound:
    def test_stop_returns_reports_for_incomplete_games(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        lm.start_round(1)
        reports = lm.stop_current_round("NEW_ROUND_STARTED")
        assert len(reports) == 2
        assert all(r.reason == "NEW_ROUND_STARTED" for r in reports)
        assert all(r.phase_at_termination == "INITIALIZED" for r in reports)
        assert len(lm.get_active_match_ids()) == 0

    def test_stop_skips_completed_games(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        # Drive game to COMPLETED
        gmc = lm.get_game(match_id)
        gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 50, "private_score": 0.5, "breakdown": {}},
            "ref@test.com",
        )
        reports = lm.stop_current_round("NEW_ROUND_STARTED")
        assert len(reports) == 0  # Completed game produces no report

    def test_start_round_auto_stops_previous(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        lm.set_assignments(2, _make_assignments(2, count=1))
        gprms, reports = lm.start_round(1)
        assert len(reports) == 0  # No previous round
        gprms, reports = lm.start_round(2)
        assert len(reports) == 2  # Round 1 games force-stopped
        assert len(lm.get_active_match_ids()) == 1  # Round 2 game active

    def test_stop_empty_round_returns_empty(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        reports = lm.stop_current_round("NEW_ROUND_STARTED")
        assert reports == []


class TestRouteQ21Message:
    def test_route_to_correct_controller(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        lm.start_round(1)
        match_ids = lm.get_active_match_ids()
        response = lm.route_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": match_ids[0], "warmup_question": "2+2"},
            "ref1@test.com",
        )
        assert response is not None
        assert response["message_type"] == Q21Handler.WARMUP_RESPONSE
        # First game advanced, second still INITIALIZED
        assert lm.get_game(match_ids[0]).phase == GamePhase.WARMUP_COMPLETE
        assert lm.get_game(match_ids[1]).phase == GamePhase.INITIALIZED

    def test_route_unknown_match_id_returns_none(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        response = lm.route_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "NONEXISTENT", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is None


class TestIsRoundComplete:
    def test_not_complete_when_games_active(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        assert lm.is_round_complete() is False

    def test_complete_when_all_games_done(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        gmc = lm.get_game(match_id)
        gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 50, "private_score": 0.5, "breakdown": {}},
            "ref@test.com",
        )
        assert lm.is_round_complete() is True
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_round_lifecycle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_infra.rlgm.round_lifecycle'`

**Step 3: Write the implementation**

```python
# _infra/rlgm/round_lifecycle.py
# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Round Lifecycle Manager — owns the current round and all its games.

Provides atomic round transitions: stop all current games, start new ones.
Routes Q21 messages to the correct per-game GMController by match_id.
Replaces RoundManager with lifecycle-aware round management.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from _infra.gmc.controller import GMController
from _infra.gmc.game_executor import PlayerAIProtocol
from _infra.gmc.q21_handler import Q21Response
from _infra.rlgm.gprm import GPRM
from _infra.rlgm.termination import GamePhase, TerminationReport

logger = logging.getLogger(__name__)


class RoundLifecycleManager:
    """Owns the current round's games with atomic transitions."""

    def __init__(
        self,
        player_ai: Optional[PlayerAIProtocol] = None,
        season_id: str = "",
        auth_token: str = "",
    ) -> None:
        self._player_ai = player_ai
        self._season_id = season_id
        self._auth_token = auth_token
        self._current_round = 0
        self._active_games: Dict[str, GMController] = {}
        self._assignments: Dict[int, List[Dict[str, Any]]] = {}

    @property
    def current_round(self) -> int:
        return self._current_round

    def set_season(self, season_id: str) -> None:
        self._season_id = season_id

    def set_auth_token(self, token: str) -> None:
        self._auth_token = token

    def set_assignments(self, round_number: int, assignments: List[Dict[str, Any]]) -> None:
        self._assignments[round_number] = assignments

    def start_round(self, round_number: int) -> Tuple[List[GPRM], List[TerminationReport]]:
        """Stop current round (if any), create new game controllers.

        Returns:
            Tuple of (GPRMs for new games, TerminationReports from stopped games).
        """
        reports = self.stop_current_round("NEW_ROUND_STARTED")
        self._current_round = round_number
        assignments = self._assignments.get(round_number, [])
        gprms = []
        for a in assignments:
            match_id = a.get("match_id", a.get("game_id", ""))
            game_id = a.get("game_id", "")
            gmc = GMController(player_ai=self._player_ai)
            gmc.initialize(
                match_id=match_id,
                game_id=game_id,
                round_number=round_number,
                season_id=self._season_id,
                referee_email=a.get("referee_email", ""),
            )
            self._active_games[match_id] = gmc
            gprms.append(self._build_gprm(a, round_number))
        return gprms, reports

    def stop_current_round(self, reason: str = "NEW_ROUND_STARTED") -> List[TerminationReport]:
        """Force-stop all active games, return reports for incomplete ones."""
        reports = []
        for match_id, gmc in self._active_games.items():
            if gmc.phase not in (GamePhase.COMPLETED, GamePhase.TERMINATED):
                reports.append(gmc.get_termination_report(reason))
                gmc.terminate()
        self._active_games.clear()
        return reports

    def route_q21_message(
        self, msg_type: str, payload: Dict[str, Any], sender: str
    ) -> Optional[dict]:
        """Route Q21 message to correct GMController by match_id."""
        match_id = payload.get("match_id", "")
        gmc = self._active_games.get(match_id)
        if gmc is None:
            logger.warning("Q21 message for unknown match_id %s — stale?", match_id)
            return None
        response = gmc.handle_q21_message(msg_type, payload, sender)
        if response is None:
            return None
        return {
            "message_type": response.message_type,
            "payload": response.payload,
            "recipient": response.recipient,
        }

    def get_game(self, match_id: str) -> Optional[GMController]:
        return self._active_games.get(match_id)

    def get_active_match_ids(self) -> List[str]:
        return list(self._active_games.keys())

    def is_round_complete(self) -> bool:
        if not self._active_games:
            return True
        return all(
            g.phase in (GamePhase.COMPLETED, GamePhase.TERMINATED)
            for g in self._active_games.values()
        )

    def _build_gprm(self, assignment: Dict[str, Any], round_number: int) -> GPRM:
        game_id = assignment.get("game_id", "")
        game_num = int(game_id[4:7]) if len(game_id) >= 7 else 1
        return GPRM(
            match_id=assignment.get("match_id", game_id),
            game_id=game_id,
            season_id=self._season_id,
            round_number=round_number,
            game_number=game_num,
            referee_email=assignment.get("referee_email", ""),
            opponent_email=assignment.get("opponent_email"),
            my_role=assignment.get("my_role", "PLAYER1"),
            book_name="",
            book_hint="",
            association_word="",
            auth_token=self._auth_token,
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_round_lifecycle.py -v`
Expected: All 11 tests PASS

**Step 5: Verify file stays under 150 lines**

Run: `wc -l _infra/rlgm/round_lifecycle.py`
Expected: ~130 lines (under 150 limit)

**Step 6: Commit**

```bash
git add _infra/rlgm/round_lifecycle.py tests/test_round_lifecycle.py
git commit -m "feat: add RoundLifecycleManager with atomic round transitions"
```

---

## Task 4: Update RLGMController to use RoundLifecycleManager

**Files:**
- Modify: `_infra/rlgm/controller.py`
- Test: `tests/test_rlgm_controller.py`

**Step 1: Write the failing tests**

```python
# tests/test_rlgm_controller.py
"""Tests for RLGMController with RoundLifecycleManager integration."""
import pytest
from unittest.mock import MagicMock
from _infra.rlgm.controller import RLGMController
from _infra.rlgm.league_handler import LeagueHandler
from _infra.gmc.q21_handler import Q21Handler
from _infra.rlgm.termination import GamePhase


def _make_mock_ai():
    ai = MagicMock()
    ai.get_warmup_answer.return_value = {"answer": "42"}
    ai.get_questions.return_value = {"questions": [{"q": "test"}]}
    ai.get_guess.return_value = {
        "opening_sentence": "It was dark.",
        "sentence_justification": "x " * 35,
        "associative_word": "dark",
        "word_justification": "x " * 35,
        "confidence": 0.8,
    }
    ai.on_score_received.return_value = None
    return ai


def _setup_controller_with_assignments():
    """Create an RLGMController with season started and assignments stored."""
    ctrl = RLGMController(
        player_email="me@test.com",
        player_name="Test",
        player_ai=_make_mock_ai(),
    )
    # Start season
    ctrl.process_message(
        LeagueHandler.START_SEASON,
        {"season_id": "S01"},
        "lgm@test.com",
    )
    # Provide assignments (two games in round 1, one in round 2)
    assignments_payload = {
        "assignments": [
            {"role": "player1", "email": "me@test.com", "game_id": "0101001", "group_id": "G1"},
            {"role": "referee", "email": "ref@test.com", "game_id": "0101001", "group_id": "G1"},
            {"role": "player2", "email": "opp@test.com", "game_id": "0101001", "group_id": "G1"},
            {"role": "player1", "email": "me@test.com", "game_id": "0101002", "group_id": "G2"},
            {"role": "referee", "email": "ref2@test.com", "game_id": "0101002", "group_id": "G2"},
            {"role": "player2", "email": "opp2@test.com", "game_id": "0101002", "group_id": "G2"},
            {"role": "player1", "email": "me@test.com", "game_id": "0102001", "group_id": "G3"},
            {"role": "referee", "email": "ref3@test.com", "game_id": "0102001", "group_id": "G3"},
            {"role": "player2", "email": "opp3@test.com", "game_id": "0102001", "group_id": "G3"},
        ],
    }
    ctrl.process_message(LeagueHandler.ASSIGNMENT_TABLE, assignments_payload, "lgm@test.com")
    return ctrl


class TestNewRoundStartsGames:
    def test_new_round_returns_gprms(self):
        ctrl = _setup_controller_with_assignments()
        response, games, reports = ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        assert len(games) == 2
        assert len(reports) == 0  # No prior round

    def test_new_round_stops_previous_round(self):
        ctrl = _setup_controller_with_assignments()
        ctrl.process_message(LeagueHandler.NEW_ROUND, {"round_number": 1}, "lgm@test.com")
        # Now start round 2 — round 1 games should be stopped
        response, games, reports = ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 2},
            "lgm@test.com",
        )
        assert len(reports) == 2  # Two round-1 games terminated
        assert len(games) == 1   # One round-2 game started


class TestQ21MessageRouting:
    def test_q21_routes_to_correct_game(self):
        ctrl = _setup_controller_with_assignments()
        ctrl.process_message(LeagueHandler.NEW_ROUND, {"round_number": 1}, "lgm@test.com")
        response = ctrl.process_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "0101001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is not None
        assert response["message_type"] == Q21Handler.WARMUP_RESPONSE

    def test_q21_stale_message_returns_none(self):
        ctrl = _setup_controller_with_assignments()
        ctrl.process_message(LeagueHandler.NEW_ROUND, {"round_number": 1}, "lgm@test.com")
        response = ctrl.process_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "STALE", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is None


class TestLeagueCompleted:
    def test_league_completed_stops_round(self):
        ctrl = _setup_controller_with_assignments()
        _, games, _ = ctrl.process_message(LeagueHandler.NEW_ROUND, {"round_number": 1}, "lgm@test.com")
        assert len(games) == 2
        response, _, reports = ctrl.process_message(
            LeagueHandler.LEAGUE_COMPLETED,
            {"final_standings": []},
            "lgm@test.com",
        )
        assert len(reports) == 2  # Both round-1 games terminated
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_rlgm_controller.py -v`
Expected: FAIL — `process_message()` returns tuple of 2, not 3

**Step 3: Rewrite RLGMController**

Replace the entire contents of `_infra/rlgm/controller.py` with:

```python
# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""RLGM Controller - League communication orchestrator.

Routes league messages and delegates game lifecycle to RoundLifecycleManager.
"""
from typing import Any, List, Optional, Tuple

from _infra.gmc.game_executor import PlayerAIProtocol
from _infra.rlgm.gprm import GPRM
from _infra.rlgm.league_handler import LeagueHandler, LeagueResponse
from _infra.rlgm.round_lifecycle import RoundLifecycleManager
from _infra.rlgm.termination import TerminationReport


class RLGMController:
    """Orchestrates league-level communication with League Manager."""

    def __init__(
        self,
        player_email: str = "",
        player_name: str = "",
        player_ai: Optional[PlayerAIProtocol] = None,
    ) -> None:
        self._player_email = player_email
        self._player_name = player_name
        self._league_handler = LeagueHandler(player_email, player_name)
        self._lifecycle = RoundLifecycleManager(player_ai=player_ai)

    def set_auth_token(self, token: str) -> None:
        self._lifecycle.set_auth_token(token)

    def process_message(
        self,
        msg_type: str,
        payload: dict[str, Any],
        sender: str,
    ) -> Tuple[Optional[LeagueResponse], List[GPRM], List[TerminationReport]]:
        """Process incoming league message.

        Returns:
            Tuple of (response, games_to_run, termination_reports).
        """
        games: List[GPRM] = []
        reports: List[TerminationReport] = []
        response: Optional[LeagueResponse] = None

        if msg_type == LeagueHandler.START_SEASON:
            response = self._league_handler.handle_start_season(payload, sender)
            season_id = payload.get("season_id", "")
            self._lifecycle.set_season(season_id)

        elif msg_type == LeagueHandler.REGISTRATION_RESPONSE:
            self._league_handler.handle_registration_response(payload)

        elif msg_type == LeagueHandler.ASSIGNMENT_TABLE:
            response = self._league_handler.handle_assignment_table(payload, sender)
            raw = payload.get("assignments", [])
            enriched = self._league_handler.parse_assignments_for_player(raw)
            by_round: dict[int, list] = {}
            for a in enriched:
                rn = a.get("round_number", 1)
                by_round.setdefault(rn, []).append(a)
            for rn, assigns in by_round.items():
                self._lifecycle.set_assignments(rn, assigns)

        elif msg_type == LeagueHandler.NEW_ROUND:
            round_number = payload.get("round_number", 1)
            games, reports = self._lifecycle.start_round(round_number)

        elif msg_type == LeagueHandler.LEAGUE_COMPLETED:
            self._league_handler.handle_league_completed(payload)
            reports = self._lifecycle.stop_current_round("LEAGUE_COMPLETED")

        else:
            raise ValueError(f"Unknown league message type: {msg_type}")

        return response, games, reports

    def process_q21_message(
        self, msg_type: str, payload: dict[str, Any], sender: str
    ) -> Optional[dict]:
        """Route Q21 message through lifecycle manager."""
        return self._lifecycle.route_q21_message(msg_type, payload, sender)

    def get_lifecycle(self) -> RoundLifecycleManager:
        return self._lifecycle

    def is_registered(self) -> bool:
        return self._league_handler.is_registered()
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_rlgm_controller.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add _infra/rlgm/controller.py tests/test_rlgm_controller.py
git commit -m "feat: wire RLGMController to RoundLifecycleManager"
```

---

## Task 5: Update RoutingResult and MessageRouter

**Files:**
- Modify: `_infra/router.py`
- Test: `tests/test_router.py`

**Step 1: Write the failing tests**

```python
# tests/test_router.py
"""Tests for MessageRouter with termination reports."""
import pytest
from unittest.mock import MagicMock
from _infra.router import MessageRouter, RoutingResult
from _infra.rlgm.league_handler import LeagueHandler
from _infra.gmc.q21_handler import Q21Handler


def _make_mock_ai():
    ai = MagicMock()
    ai.get_warmup_answer.return_value = {"answer": "42"}
    ai.get_questions.return_value = {"questions": []}
    ai.get_guess.return_value = {
        "opening_sentence": "X", "sentence_justification": "x " * 35,
        "associative_word": "y", "word_justification": "x " * 35, "confidence": 0.5,
    }
    ai.on_score_received.return_value = None
    return ai


class TestRoutingResult:
    def test_termination_reports_default_empty(self):
        r = RoutingResult(response=None, games_to_run=[], handled=True)
        assert r.termination_reports == []

    def test_termination_reports_populated(self):
        r = RoutingResult(
            response=None, games_to_run=[], handled=True,
            termination_reports=[{"match_id": "M001"}],
        )
        assert len(r.termination_reports) == 1


class TestRouterRoundTransition:
    def test_new_round_returns_termination_reports(self):
        router = MessageRouter(player_email="me@test.com", player_name="T", player_ai=_make_mock_ai())
        # Start season + assignments
        router.route_message(LeagueHandler.START_SEASON, {"season_id": "S01"}, "lgm@test.com")
        router.route_message(LeagueHandler.ASSIGNMENT_TABLE, {
            "assignments": [
                {"role": "player1", "email": "me@test.com", "game_id": "0101001", "group_id": "G1"},
                {"role": "referee", "email": "ref@test.com", "game_id": "0101001", "group_id": "G1"},
                {"role": "player2", "email": "opp@test.com", "game_id": "0101001", "group_id": "G1"},
            ],
        }, "lgm@test.com")
        # Start round 1
        result = router.route_message(LeagueHandler.NEW_ROUND, {"round_number": 1}, "lgm@test.com")
        assert len(result.games_to_run) == 1
        assert len(result.termination_reports) == 0
        # Start round 2 — round 1 game terminated
        router.route_message(LeagueHandler.ASSIGNMENT_TABLE, {
            "assignments": [
                {"role": "player1", "email": "me@test.com", "game_id": "0102001", "group_id": "G2"},
                {"role": "referee", "email": "ref2@test.com", "game_id": "0102001", "group_id": "G2"},
                {"role": "player2", "email": "opp2@test.com", "game_id": "0102001", "group_id": "G2"},
            ],
        }, "lgm@test.com")
        result = router.route_message(LeagueHandler.NEW_ROUND, {"round_number": 2}, "lgm@test.com")
        assert len(result.termination_reports) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_router.py -v`
Expected: FAIL — `RoutingResult` has no `termination_reports` field

**Step 3: Update router.py**

Update `_infra/router.py` — add `termination_reports` to `RoutingResult` and update `_route_league_message` to unpack the 3-tuple from `RLGMController.process_message()`:

Changes to make:
1. Add `from dataclasses import dataclass, field` (add `field` import)
2. Add `termination_reports: List[dict] = field(default_factory=list)` to `RoutingResult`
3. Update `_route_league_message` to unpack `(response, games, reports)` and convert reports
4. Remove unused imports: `Q21Handler`, `LeagueHandler` (only used by `RLGMController` now)

The full updated file:

```python
# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Message Router - unified routing for all protocol messages.

Provides a single entry point for routing messages to either
RLGM (league messages) or GMC (game messages).
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional

from _infra.gmc.game_executor import PlayerAIProtocol
from _infra.rlgm.controller import RLGMController
from _infra.rlgm.gprm import GPRM


@dataclass
class RoutingResult:
    """Result of message routing."""
    response: Optional[dict]
    games_to_run: List[GPRM]
    handled: bool
    termination_reports: List[dict] = field(default_factory=list)


class MessageRouter:
    """Routes protocol messages to RLGM or GMC."""

    LEAGUE_PREFIXES = ("BROADCAST_", "SEASON_REGISTRATION", "LEAGUE_")
    Q21_PREFIX = "Q21"

    def __init__(
        self,
        player_email: str = "",
        player_name: str = "",
        player_ai: Optional[PlayerAIProtocol] = None,
    ) -> None:
        self._rlgm = RLGMController(
            player_email=player_email,
            player_name=player_name,
            player_ai=player_ai,
        )

    def set_auth_token(self, token: str) -> None:
        self._rlgm.set_auth_token(token)

    def route_message(
        self, msg_type: str, payload: dict[str, Any], sender: str
    ) -> RoutingResult:
        if self._is_league_message(msg_type):
            return self._route_league_message(msg_type, payload, sender)
        if self._is_q21_message(msg_type):
            return self._route_q21_message(msg_type, payload, sender)
        return RoutingResult(response=None, games_to_run=[], handled=False)

    def _is_league_message(self, msg_type: str) -> bool:
        return any(msg_type.startswith(p) for p in self.LEAGUE_PREFIXES)

    def _is_q21_message(self, msg_type: str) -> bool:
        return msg_type.startswith(self.Q21_PREFIX)

    def _route_league_message(
        self, msg_type: str, payload: dict[str, Any], sender: str
    ) -> RoutingResult:
        league_response, games, reports = self._rlgm.process_message(
            msg_type, payload, sender
        )
        response = None
        if league_response is not None:
            response = {
                "message_type": league_response.message_type,
                "payload": league_response.payload,
                "recipient": league_response.recipient,
            }
        term_reports = [r.to_protocol_message("", "") for r in reports]
        return RoutingResult(
            response=response,
            games_to_run=games,
            handled=True,
            termination_reports=term_reports,
        )

    def _route_q21_message(
        self, msg_type: str, payload: dict[str, Any], sender: str
    ) -> RoutingResult:
        response = self._rlgm.process_q21_message(msg_type, payload, sender)
        return RoutingResult(response=response, games_to_run=[], handled=True)

    def get_rlgm(self) -> RLGMController:
        return self._rlgm

    def is_registered(self) -> bool:
        return self._rlgm.is_registered()
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/test_router.py -v`
Expected: All 3 tests PASS

**Step 5: Run ALL tests to verify no regressions**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/ -v`
Expected: All tests across all test files PASS

**Step 6: Commit**

```bash
git add _infra/router.py tests/test_router.py
git commit -m "feat: add termination_reports to RoutingResult and update MessageRouter"
```

---

## Task 6: Remove old RoundManager (cleanup)

**Files:**
- Delete: `_infra/rlgm/round_manager.py`
- Verify no imports remain

**Step 1: Search for remaining imports of round_manager**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && grep -r "round_manager" _infra/ tests/`
Expected: No matches (RLGMController no longer imports it)

**Step 2: Delete the file**

```bash
git rm _infra/rlgm/round_manager.py
```

**Step 3: Run all tests to verify nothing breaks**

Run: `cd /Users/work/Desktop/Folders/Q21G-whl/Q21G-player-whl && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git commit -m "refactor: remove RoundManager (subsumed by RoundLifecycleManager)"
```

---

## Task 7: Update PRD and CLAUDE.md

**Files:**
- Modify: `docs/prd-rlgm.md` — increment version, add RoundLifecycleManager section, update architecture
- Modify: `CLAUDE.md` — update project structure to reflect new files

**Step 1: Read current PRD**

Run: Read `docs/prd-rlgm.md` to understand current content and version

**Step 2: Update PRD**

Add these sections/changes:
- Increment version (e.g., 2.0.0 → 3.0.0)
- Add `RoundLifecycleManager` to the component descriptions
- Add `TerminationReport` and `GamePhase` to the data model section
- Document round transition flow
- Document `MATCH_RESULT_REPORT` protocol message
- Remove references to `RoundManager`

**Step 3: Update CLAUDE.md project structure**

Replace `round_manager.py` with `round_lifecycle.py` and add `termination.py` in the project structure tree.

**Step 4: Commit**

```bash
git add docs/prd-rlgm.md CLAUDE.md
git commit -m "docs: update PRD and CLAUDE.md for round lifecycle reform"
```

---

## Task Summary

| Task | Creates/Modifies | Tests | Est. Lines |
|------|-----------------|-------|------------|
| 1. GamePhase + TerminationReport | `_infra/rlgm/termination.py` | `tests/test_termination.py` | ~50 |
| 2. GMController phase tracking | `_infra/gmc/controller.py` | `tests/test_gmc_controller.py` | ~130 |
| 3. RoundLifecycleManager | `_infra/rlgm/round_lifecycle.py` | `tests/test_round_lifecycle.py` | ~130 |
| 4. RLGMController integration | `_infra/rlgm/controller.py` | `tests/test_rlgm_controller.py` | ~80 |
| 5. RoutingResult + MessageRouter | `_infra/router.py` | `tests/test_router.py` | ~85 |
| 6. Remove RoundManager | delete `round_manager.py` | verify no breakage | 0 |
| 7. Update docs | `prd-rlgm.md`, `CLAUDE.md` | N/A | docs |
