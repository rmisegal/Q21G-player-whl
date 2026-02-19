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
