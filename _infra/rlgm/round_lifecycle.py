# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Round Lifecycle Manager - owns the current round and all its games."""
import logging
from typing import Any, Dict, List, Optional, Tuple

from _infra.gmc.controller import GMController
from _infra.gmc.game_executor import PlayerAIProtocol
from _infra.gmc.q21_handler import Q21Response
from _infra.rlgm.gprm import GPRM
from _infra.rlgm.termination import GamePhase, MatchReport

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

    def set_assignments(
        self, round_number: int, assignments: List[Dict[str, Any]]
    ) -> None:
        self._assignments[round_number] = assignments

    def has_assignments_for_round(self, round_number: int) -> bool:
        """Check if assignments exist for a given round."""
        return bool(self._assignments.get(round_number, []))

    def start_round(
        self, round_number: int
    ) -> Tuple[List[GPRM], List[MatchReport]]:
        """Stop current round (if any), create new game controllers."""
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

    def stop_current_round(
        self, reason: str = "NEW_ROUND_STARTED"
    ) -> List[MatchReport]:
        """Force-stop all active games, return reports for incomplete."""
        reports: List[MatchReport] = []
        for match_id, gmc in self._active_games.items():
            if gmc.phase not in (GamePhase.COMPLETED, GamePhase.TERMINATED):
                reports.append(gmc.get_match_report(reason))
                gmc.terminate()
        self._active_games.clear()
        return reports

    def route_q21_message(
        self, msg_type: str, payload: Dict[str, Any], sender: str
    ) -> Tuple[Optional[dict], List[MatchReport]]:
        """Route Q21 message to correct GMController by match_id."""
        match_id = payload.get("match_id", "")
        gmc = self._active_games.get(match_id)
        if gmc is None:
            logger.warning(
                "Q21 message for unknown match_id %s - stale?", match_id
            )
            return None, []
        if gmc.phase in (GamePhase.COMPLETED, GamePhase.TERMINATED):
            logger.warning(
                "Q21 message for %s game %s - ignoring",
                gmc.phase.value, match_id,
            )
            return None, []
        response = gmc.handle_q21_message(msg_type, payload, sender)
        reports: List[MatchReport] = []
        if gmc.phase == GamePhase.COMPLETED:
            reports.append(gmc.get_match_report("GAME_COMPLETED"))
        resp_dict = None
        if response is not None:
            resp_dict = {
                "message_type": response.message_type,
                "payload": response.payload,
                "recipient": response.recipient,
            }
        return resp_dict, reports

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

    def _build_gprm(
        self, assignment: Dict[str, Any], round_number: int
    ) -> GPRM:
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
