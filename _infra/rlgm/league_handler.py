"""League Handler - handles League Manager broadcast messages.

Processes all BROADCAST_* messages from the League Manager
and generates appropriate responses.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LeagueResponse:
    """Response to send back to League Manager."""
    message_type: str
    payload: Dict[str, Any]
    recipient: str


class LeagueHandler:
    """Handles League Manager broadcast messages.

    Message types handled:
    - BROADCAST_START_SEASON -> SEASON_REGISTRATION_REQUEST
    - SEASON_REGISTRATION_RESPONSE -> (acknowledgment)
    - BROADCAST_ASSIGNMENT_TABLE -> GROUP_ASSIGNMENT_RESPONSE
    - BROADCAST_NEW_LEAGUE_ROUND -> (triggers games)
    - BROADCAST_ROUND_RESULTS -> (updates scores)
    - BROADCAST_KEEP_ALIVE -> KEEP_ALIVE_RESPONSE
    - BROADCAST_CRITICAL_* -> CRITICAL_*_RESPONSE
    - LEAGUE_COMPLETED -> (finalize season)
    """

    # Message type constants
    START_SEASON = "BROADCAST_START_SEASON"
    REGISTRATION_RESPONSE = "SEASON_REGISTRATION_RESPONSE"
    ASSIGNMENT_TABLE = "BROADCAST_ASSIGNMENT_TABLE"
    NEW_ROUND = "BROADCAST_NEW_LEAGUE_ROUND"
    ROUND_RESULTS = "BROADCAST_ROUND_RESULTS"
    KEEP_ALIVE = "BROADCAST_KEEP_ALIVE"
    CRITICAL_PAUSE = "BROADCAST_CRITICAL_PAUSE"
    CRITICAL_CONTINUE = "BROADCAST_CRITICAL_CONTINUE"
    CRITICAL_RESET = "BROADCAST_CRITICAL_RESET"
    LEAGUE_COMPLETED = "LEAGUE_COMPLETED"

    def __init__(self, player_email: str = "", player_name: str = "") -> None:
        """Initialize the LeagueHandler.

        Args:
            player_email: Player's email address.
            player_name: Player's display name.
        """
        self._player_email = player_email
        self._player_name = player_name
        self._registered = False
        self._season_id: Optional[str] = None
        # Score tracking for callback optimization
        self._total_score: float = 0.0
        self._games_played: int = 0
        self._rank: int = 0

    def handle_start_season(
        self,
        payload: Dict[str, Any],
        sender: str
    ) -> LeagueResponse:
        """Handle BROADCAST_START_SEASON - register for the season.

        Args:
            payload: Start season payload with season_id, etc.
            sender: League Manager email.

        Returns:
            LeagueResponse with SEASON_REGISTRATION_REQUEST.
        """
        self._season_id = payload.get("season_id", "")

        return LeagueResponse(
            message_type="SEASON_REGISTRATION_REQUEST",
            payload={
                "season_id": self._season_id,
                "player_email": self._player_email,
                "player_name": self._player_name,
                "machine_state": "READY",
            },
            recipient=sender,
        )

    def handle_registration_response(
        self,
        payload: Dict[str, Any]
    ) -> None:
        """Handle SEASON_REGISTRATION_RESPONSE - confirm registration.

        Args:
            payload: Registration response with status.
        """
        status = payload.get("status", "")
        if status in ("REGISTERED", "ACCEPTED", "OK"):
            self._registered = True

    def is_registered(self) -> bool:
        """Check if player is registered for current season."""
        return self._registered

    def get_season_id(self) -> Optional[str]:
        """Get current season ID."""
        return self._season_id

    def handle_assignment_table(
        self,
        payload: Dict[str, Any],
        sender: str
    ) -> LeagueResponse:
        """Handle BROADCAST_ASSIGNMENT_TABLE - acknowledge assignments.

        Args:
            payload: Assignment table with round assignments.
            sender: League Manager email.

        Returns:
            LeagueResponse with GROUP_ASSIGNMENT_RESPONSE.
        """
        round_number = payload.get("round_number", 1)
        assignments = payload.get("assignments", [])

        # Filter assignments for this player
        my_assignments = [
            a for a in assignments
            if a.get("player_email") == self._player_email
            or a.get("player_a_email") == self._player_email
            or a.get("player_b_email") == self._player_email
        ]

        return LeagueResponse(
            message_type="GROUP_ASSIGNMENT_RESPONSE",
            payload={
                "season_id": self._season_id,
                "round_number": round_number,
                "player_email": self._player_email,
                "assignments_received": len(my_assignments),
                "status": "ACKNOWLEDGED",
            },
            recipient=sender,
        )

    def handle_new_league_round(
        self,
        payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Handle BROADCAST_NEW_LEAGUE_ROUND - prepare for games.

        Args:
            payload: New round payload with round info.

        Returns:
            List of assignment dicts for the round.
        """
        round_number = payload.get("round_number", 1)
        assignments = payload.get("assignments", [])

        # Filter and enrich assignments for this player
        my_assignments = []
        for a in assignments:
            is_player_a = a.get("player_a_email") == self._player_email
            is_player_b = a.get("player_b_email") == self._player_email
            is_player = a.get("player_email") == self._player_email

            if is_player_a or is_player_b or is_player:
                enriched = {
                    "match_id": a.get("match_id", ""),
                    "game_id": a.get("game_id", ""),
                    "round_number": round_number,
                    "referee_email": a.get("referee_email", ""),
                    "my_role": "PLAYER_A" if is_player_a else "PLAYER_B",
                    "book_name": a.get("book_name", ""),
                    "book_hint": a.get("book_hint", a.get("book_description", "")),
                    "association_domain": a.get("association_domain", ""),
                }
                # Add opponent email
                if is_player_a:
                    enriched["opponent_email"] = a.get("player_b_email")
                elif is_player_b:
                    enriched["opponent_email"] = a.get("player_a_email")

                my_assignments.append(enriched)

        return my_assignments

    def handle_round_results(
        self,
        payload: Dict[str, Any]
    ) -> None:
        """Handle BROADCAST_ROUND_RESULTS - update internal scores.

        Updates internal score tracking for callback optimization.
        The player can use this to adjust strategy based on standings.

        Args:
            payload: Round results with standings.
        """
        standings = payload.get("standings", [])

        # Find this player's position in standings
        for i, entry in enumerate(standings, 1):
            if entry.get("player_email") == self._player_email:
                self._total_score = float(entry.get("total_score", 0.0))
                self._games_played = int(entry.get("games_played", 0))
                self._rank = i
                break

    def handle_keep_alive(
        self,
        payload: Dict[str, Any],
        sender: str
    ) -> LeagueResponse:
        """Handle BROADCAST_KEEP_ALIVE - respond to heartbeat.

        Args:
            payload: Keep alive payload.
            sender: League Manager email.

        Returns:
            LeagueResponse with KEEP_ALIVE_RESPONSE.
        """
        return LeagueResponse(
            message_type="KEEP_ALIVE_RESPONSE",
            payload={
                "player_email": self._player_email,
                "machine_state": "READY",
                "season_id": self._season_id,
            },
            recipient=sender,
        )

    def get_standings(self) -> Dict[str, Any]:
        """Get current standings for this player.

        Returns:
            Dict with total_score, games_played, and rank.
        """
        return {
            "total_score": self._total_score,
            "games_played": self._games_played,
            "rank": self._rank,
        }

    def handle_critical_pause(
        self,
        payload: Dict[str, Any],
        sender: str
    ) -> LeagueResponse:
        """Handle BROADCAST_CRITICAL_PAUSE - acknowledge pause.

        Args:
            payload: Pause payload with reason.
            sender: League Manager email.

        Returns:
            LeagueResponse with CRITICAL_PAUSE_RESPONSE.
        """
        return LeagueResponse(
            message_type="CRITICAL_PAUSE_RESPONSE",
            payload={
                "player_email": self._player_email,
                "status": "PAUSED",
                "season_id": self._season_id,
            },
            recipient=sender,
        )

    def handle_critical_continue(
        self,
        payload: Dict[str, Any],
        sender: str
    ) -> LeagueResponse:
        """Handle BROADCAST_CRITICAL_CONTINUE - acknowledge continue.

        Args:
            payload: Continue payload.
            sender: League Manager email.

        Returns:
            LeagueResponse with CRITICAL_CONTINUE_RESPONSE.
        """
        return LeagueResponse(
            message_type="CRITICAL_CONTINUE_RESPONSE",
            payload={
                "player_email": self._player_email,
                "status": "RESUMED",
                "season_id": self._season_id,
            },
            recipient=sender,
        )

    def handle_critical_reset(
        self,
        payload: Dict[str, Any],
        sender: str
    ) -> LeagueResponse:
        """Handle BROADCAST_CRITICAL_RESET - acknowledge and reset state.

        Args:
            payload: Reset payload.
            sender: League Manager email.

        Returns:
            LeagueResponse with CRITICAL_RESET_RESPONSE.
        """
        # Reset internal state
        self._total_score = 0.0
        self._games_played = 0
        self._rank = 0

        return LeagueResponse(
            message_type="CRITICAL_RESET_RESPONSE",
            payload={
                "player_email": self._player_email,
                "status": "RESET_COMPLETE",
                "season_id": self._season_id,
            },
            recipient=sender,
        )

    def handle_league_completed(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle LEAGUE_COMPLETED - finalize season.

        GAP FIX #2: This method was missing in the original
        GmailAsPlayer implementation.

        Args:
            payload: League completed payload with final standings.

        Returns:
            Dict with final standings info.
        """
        final_standings = payload.get("final_standings", [])
        winner = payload.get("winner", {})

        # Update final standings for this player
        for i, entry in enumerate(final_standings, 1):
            if entry.get("player_email") == self._player_email:
                self._total_score = float(entry.get("total_score", 0.0))
                self._games_played = int(entry.get("games_played", 0))
                self._rank = i
                break

        return {
            "season_id": self._season_id,
            "final_rank": self._rank,
            "final_score": self._total_score,
            "games_played": self._games_played,
            "winner_email": winner.get("player_email", ""),
            "season_complete": True,
        }
