# Area: GMC (Game Manager Component)
# PRD: docs/prd-rlgm.md
"""GMC Controller - manages a single Q21 game lifecycle with phase tracking."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from _infra.gmc.game_executor import GameExecutor, PlayerAIProtocol
from _infra.gmc.q21_handler import Q21Handler, Q21Response

if TYPE_CHECKING:
    from _infra.rlgm.termination import GamePhase, MatchReport


def _get_phase_module():
    """Lazy import to avoid circular dependency with rlgm package."""
    from _infra.rlgm.termination import GamePhase, MatchReport
    return GamePhase, MatchReport


def _phase_last_actor(phase) -> str:
    """Return last_actor string for a given phase."""
    GP, _ = _get_phase_module()
    return {
        GP.INITIALIZED: "NONE", GP.WARMUP_COMPLETE: "PLAYER",
        GP.QUESTIONS_SENT: "PLAYER", GP.GUESS_SUBMITTED: "PLAYER",
        GP.COMPLETED: "NONE", GP.TERMINATED: "NONE",
    }.get(phase, "NONE")


class GMController:
    """Orchestrates a single Q21 game lifecycle with phase tracking."""

    def __init__(self, player_ai: Optional[PlayerAIProtocol] = None) -> None:
        GP, _ = _get_phase_module()
        self._executor = GameExecutor(player_ai=player_ai)
        self._phase = GP.INITIALIZED
        self._match_id = ""
        self._game_id = ""
        self._round_number = 0
        self._season_id = ""
        self._referee_email = ""
        self._last_sent: Optional[str] = None
        self._last_received: Optional[str] = None
        self._league_points: Optional[int] = None
        self._private_score: Optional[float] = None
        self._breakdown: Optional[dict] = None

    def initialize(self, match_id: str, game_id: str, round_number: int,
                   season_id: str, referee_email: str) -> None:
        """Set up controller for a specific game."""
        GP, _ = _get_phase_module()
        self._match_id = match_id
        self._game_id = game_id
        self._round_number = round_number
        self._season_id = season_id
        self._referee_email = referee_email
        self._phase = GP.INITIALIZED

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

    def handle_q21_message(self, msg_type: str, payload: dict[str, Any],
                           sender: str) -> Optional[Q21Response]:
        """Handle Q21 message. Updates phase and message history."""
        GP, _ = _get_phase_module()
        match_id = payload.get("match_id", "")

        if msg_type == Q21Handler.WARMUP_CALL:
            self._last_received = Q21Handler.WARMUP_CALL
            result = self._executor.execute_warmup(payload)
            self._last_sent = Q21Handler.WARMUP_RESPONSE
            self._phase = GP.WARMUP_COMPLETE
            return Q21Response(
                message_type=Q21Handler.WARMUP_RESPONSE,
                payload={"match_id": match_id, "answer": result["warmup_answer"]},
                recipient=sender,
            )
        elif msg_type == Q21Handler.ROUND_START:
            self._last_received = Q21Handler.ROUND_START
            self._executor.handle_round_start(payload)
            qr = self._executor.execute_questions(payload)
            self._last_sent = Q21Handler.QUESTIONS_BATCH
            self._phase = GP.QUESTIONS_SENT
            return Q21Response(
                message_type=Q21Handler.QUESTIONS_BATCH,
                payload={"match_id": match_id, "questions": qr["questions"]},
                recipient=sender,
            )
        elif msg_type == Q21Handler.ANSWERS_BATCH:
            self._last_received = Q21Handler.ANSWERS_BATCH
            result = self._executor.receive_answers(payload)
            guess_payload = {**payload, "answers": result["answers"]}
            guess_result = self._executor.execute_guess(guess_payload)
            self._last_sent = Q21Handler.GUESS_SUBMISSION
            self._phase = GP.GUESS_SUBMITTED
            return Q21Response(
                message_type=Q21Handler.GUESS_SUBMISSION,
                payload={"match_id": match_id, "guess": guess_result["guess"]},
                recipient=sender,
            )
        elif msg_type == Q21Handler.SCORE_FEEDBACK:
            self._last_received = Q21Handler.SCORE_FEEDBACK
            self._league_points = payload.get("league_points")
            self._private_score = payload.get("private_score")
            self._breakdown = payload.get("breakdown")
            self._executor.handle_score(payload)
            self._phase = GP.COMPLETED
            return None
        else:
            raise ValueError(f"Unknown Q21 message type: {msg_type}")

    def get_match_report(self, reason: str) -> MatchReport:
        """Snapshot current state for match reporting."""
        GP, MR = _get_phase_module()
        status = "COMPLETED" if self._phase == GP.COMPLETED else "TERMINATED"
        return MR(
            match_id=self._match_id, game_id=self._game_id,
            round_number=self._round_number, season_id=self._season_id,
            status=status,
            phase_at_termination=self._phase.value,
            last_actor=_phase_last_actor(self._phase),
            last_message_sent=self._last_sent or "",
            last_message_received=self._last_received or "",
            reported_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            league_points=self._league_points,
            private_score=self._private_score,
            breakdown=self._breakdown,
        )

    def terminate(self) -> None:
        """Mark game as TERMINATED."""
        GP, _ = _get_phase_module()
        self._phase = GP.TERMINATED
