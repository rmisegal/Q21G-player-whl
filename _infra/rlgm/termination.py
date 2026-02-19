# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Game phase tracking and match reporting.

Provides GamePhase enum for explicit phase tracking in GMController,
and MatchReport for capturing game state on completion or force-stop.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GamePhase(Enum):
    """Phases of a Q21 game lifecycle."""
    INITIALIZED = "INITIALIZED"
    WARMUP_COMPLETE = "WARMUP_COMPLETE"
    QUESTIONS_SENT = "QUESTIONS_SENT"
    GUESS_SUBMITTED = "GUESS_SUBMITTED"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


@dataclass
class MatchReport:
    """Snapshot of game state at completion or forced termination.

    Created when a game completes normally or when a round transition
    force-stops an incomplete game. Used to generate MATCH_RESULT_REPORT
    protocol messages to LGM.
    """
    match_id: str
    game_id: str
    round_number: int
    season_id: str
    status: str                  # "COMPLETED" or "TERMINATED"
    phase_at_termination: str
    last_actor: str              # "PLAYER", "REFEREE", or "NONE"
    last_message_sent: str       # Last msg type player sent
    last_message_received: str   # Last msg type player received
    reported_at: str             # ISO timestamp
    reason: str                  # e.g. "GAME_COMPLETED", "NEW_ROUND_STARTED"
    league_points: Optional[int] = None
    private_score: Optional[float] = None
    breakdown: Optional[dict] = None

    def to_protocol_message(
        self, reporter_email: str, reporter_role: str
    ) -> dict:
        """Convert to MATCH_RESULT_REPORT protocol message."""
        msg = {
            "message_type": "MATCH_RESULT_REPORT",
            "version": "1.0",
            "match_id": self.match_id,
            "game_id": self.game_id,
            "round_number": self.round_number,
            "season_id": self.season_id,
            "status": self.status,
            "phase_at_termination": self.phase_at_termination,
            "last_actor": self.last_actor,
            "last_message_sent": self.last_message_sent,
            "last_message_received": self.last_message_received,
            "reported_at": self.reported_at,
            "reason": self.reason,
            "reporter": {
                "email": reporter_email,
                "role": reporter_role,
            },
        }
        if self.league_points is not None:
            msg["league_points"] = self.league_points
        if self.private_score is not None:
            msg["private_score"] = self.private_score
        if self.breakdown is not None:
            msg["breakdown"] = self.breakdown
        return msg
