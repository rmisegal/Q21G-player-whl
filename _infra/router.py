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
        """Set authentication token."""
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
        """Route league message to RLGM."""
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
        """Route Q21 message to GMC."""
        response = self._rlgm.process_q21_message(msg_type, payload, sender)
        return RoutingResult(response=response, games_to_run=[], handled=True)

    def get_rlgm(self) -> RLGMController:
        """Get the RLGM controller for direct access."""
        return self._rlgm

    def is_registered(self) -> bool:
        """Check if player is registered."""
        return self._rlgm.is_registered()
