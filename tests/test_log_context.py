# Area: Protocol Logging
# PRD: docs/LOGGER_OUTPUT_PLAYER.md
"""Tests for log_context.set_logging_context role determination.

Per PRD section 5.2/5.3:
- Q21 messages (game-level) -> always PLAYER-ACTIVE
- START-ROUND with assignments -> PLAYER-ACTIVE
- START-ROUND without assignments -> PLAYER-INACTIVE
- Season-level messages -> no role (set_season_context)
"""
import pytest
from unittest.mock import patch, MagicMock

from q21_player._infra.cli.log_context import set_logging_context

MODULE = "q21_player._infra.cli.log_context"


@pytest.fixture
def mock_repo():
    return MagicMock()


class TestQ21MessagesAlwaysActive:
    """Q21 messages mean the referee is talking to us -> PLAYER-ACTIVE."""

    Q21_TYPES = [
        "Q21WARMUPCALL",
        "Q21ROUNDSTART",
        "Q21ANSWERSBATCH",
        "Q21SCOREFEEDBACK",
    ]

    @pytest.mark.parametrize("msg_type", Q21_TYPES)
    @patch(f"{MODULE}.set_game_context")
    def test_q21_sets_player_active_true(
        self, mock_set_ctx, msg_type, mock_repo
    ):
        game_id = "TRAIN_2026-02-11_0900_0102001"
        mock_repo.get_by_game_id.return_value = None  # not in DB

        set_logging_context(msg_type, game_id, {}, {}, mock_repo, None)

        mock_set_ctx.assert_called_once_with(game_id, True)

    @patch(f"{MODULE}.set_game_context")
    def test_q21_active_even_with_7digit_game_id(
        self, mock_set_ctx, mock_repo
    ):
        mock_repo.get_by_game_id.return_value = None

        set_logging_context("Q21WARMUPCALL", "0102001", {}, {}, mock_repo, None)

        mock_set_ctx.assert_called_once_with("0102001", True)


class TestStartRoundRoleDetermination:
    """START-ROUND role depends on assignment table."""

    @patch(f"{MODULE}.set_round_context")
    def test_round_with_assignments_is_active(
        self, mock_set_ctx, mock_repo
    ):
        assignment = MagicMock(my_role="PLAYER")
        mock_repo.get_by_round.return_value = [assignment]

        set_logging_context(
            "BROADCASTNEWLEAGUEROUND", "", {"round_number": 2},
            {}, mock_repo, "S01"
        )

        mock_set_ctx.assert_called_once_with(2, True)

    @patch(f"{MODULE}.set_round_context")
    def test_round_without_assignments_is_inactive(
        self, mock_set_ctx, mock_repo
    ):
        mock_repo.get_by_round.return_value = []

        set_logging_context(
            "BROADCASTNEWLEAGUEROUND", "", {"round_number": 3},
            {}, mock_repo, "S01"
        )

        mock_set_ctx.assert_called_once_with(3, False)


class TestSeasonLevelMessages:
    """Season-level messages use set_season_context (no role)."""

    @patch(f"{MODULE}.set_season_context")
    def test_start_season_uses_season_context(
        self, mock_set_ctx, mock_repo
    ):
        set_logging_context(
            "BROADCASTSTARTSEASON", "", {}, {}, mock_repo, None
        )

        mock_set_ctx.assert_called_once()
