"""GPRM (Game Parameters) and GameResult dataclasses.

GPRM represents the immutable input data needed to run a single Q21 game.
GameResult represents the output returned by GMC after game completion.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class GPRM:
    """Game Parameters - immutable input to GMC.

    Contains all information needed to execute a single Q21 game match.
    """
    # Identity
    match_id: str           # e.g., "S1R2G003"
    game_id: str            # e.g., "0102003"
    season_id: str          # e.g., "SEASON01"
    round_number: int       # e.g., 2
    game_number: int        # e.g., 3

    # Participants
    referee_email: str      # From assignment
    opponent_email: Optional[str]  # May be None for solo games
    my_role: str            # "PLAYER_A", "PLAYER_B", or "QUESTIONER"

    # Game content
    book_name: str          # Book/lecture title
    book_hint: str          # Description (15 words)
    association_domain: str # Domain for associative word

    # Authentication
    auth_token: str


@dataclass
class GameResult:
    """Result returned by GMC after game completion.

    Contains scoring information and status of the completed game.
    """
    match_id: str
    game_id: str
    status: str             # COMPLETED, FAILED, TIMEOUT
    league_points: int      # 0-100 league points
    private_score: float    # Internal scoring metric
    breakdown: dict = field(default_factory=dict)  # Detailed score breakdown
    error: Optional[str] = None  # Error message if status is FAILED


class GPRMBuilder:
    """Builder for constructing GPRM objects from various sources.

    Provides a fluent interface for building GPRM objects from
    assignment data, message payloads, or explicit values.
    """

    def __init__(self, season_id: str = "", auth_token: str = "") -> None:
        """Initialize the builder with defaults.

        Args:
            season_id: Default season ID for built GPRMs.
            auth_token: Default auth token for built GPRMs.
        """
        self._season_id = season_id
        self._auth_token = auth_token

    def set_season_id(self, season_id: str) -> "GPRMBuilder":
        """Set the season ID."""
        self._season_id = season_id
        return self

    def set_auth_token(self, token: str) -> "GPRMBuilder":
        """Set the authentication token."""
        self._auth_token = token
        return self

    def build_from_assignment(self, assignment: dict) -> GPRM:
        """Build GPRM from assignment dictionary.

        Args:
            assignment: Assignment dict with keys like match_id, referee_email,
                       book_name, etc.

        Returns:
            Constructed GPRM object.
        """
        round_num = assignment.get("round_number", 1)
        game_num = assignment.get("game_number", 1)

        return GPRM(
            match_id=assignment.get("match_id", f"S{self._season_id}R{round_num}G{game_num:03d}"),
            game_id=assignment.get("game_id", f"{round_num:02d}{game_num:03d}"),
            season_id=self._season_id,
            round_number=round_num,
            game_number=game_num,
            referee_email=assignment.get("referee_email", ""),
            opponent_email=assignment.get("opponent_email"),
            my_role=assignment.get("my_role", "PLAYER_A"),
            book_name=assignment.get("book_name", ""),
            book_hint=assignment.get("book_hint", assignment.get("book_description", "")),
            association_domain=assignment.get("association_domain", ""),
            auth_token=assignment.get("auth_token", self._auth_token),
        )
