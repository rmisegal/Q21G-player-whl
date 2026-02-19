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
from _infra.rlgm.termination import MatchReport


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
        """Set authentication token for game requests."""
        self._lifecycle.set_auth_token(token)

    def process_message(
        self,
        msg_type: str,
        payload: dict[str, Any],
        sender: str,
    ) -> Tuple[Optional[LeagueResponse], List[GPRM], List[MatchReport]]:
        """Process incoming league message.

        Returns:
            Tuple of (response, games_to_run, match_reports).
        """
        games: List[GPRM] = []
        reports: List[MatchReport] = []
        response: Optional[LeagueResponse] = None

        if msg_type == LeagueHandler.START_SEASON:
            response = self._league_handler.handle_start_season(
                payload, sender
            )
            season_id = payload.get("season_id", "")
            self._lifecycle.set_season(season_id)

        elif msg_type == LeagueHandler.REGISTRATION_RESPONSE:
            self._league_handler.handle_registration_response(payload)

        elif msg_type == LeagueHandler.ASSIGNMENT_TABLE:
            response = self._league_handler.handle_assignment_table(
                payload, sender
            )
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
    ) -> Tuple[Optional[dict], List[MatchReport]]:
        """Route Q21 message through lifecycle manager."""
        return self._lifecycle.route_q21_message(msg_type, payload, sender)

    def get_lifecycle(self) -> RoundLifecycleManager:
        """Get the RoundLifecycleManager for direct access."""
        return self._lifecycle

    def is_registered(self) -> bool:
        """Check if player is registered."""
        return self._league_handler.is_registered()
