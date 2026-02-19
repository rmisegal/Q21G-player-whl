# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Tests for MessageRouter with match reports."""
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
        "associative_word": "y", "word_justification": "x " * 35,
        "confidence": 0.5,
    }
    ai.on_score_received.return_value = None
    return ai


class TestRoutingResult:
    def test_match_reports_default_empty(self):
        r = RoutingResult(response=None, games_to_run=[], handled=True)
        assert r.match_reports == []

    def test_match_reports_populated(self):
        r = RoutingResult(
            response=None, games_to_run=[], handled=True,
            match_reports=[{"match_id": "M001"}],
        )
        assert len(r.match_reports) == 1


class TestRouterRoundTransition:
    def test_new_round_returns_match_reports(self):
        router = MessageRouter(
            player_email="me@test.com",
            player_name="T",
            player_ai=_make_mock_ai(),
        )
        # Start season + assignments
        router.route_message(
            LeagueHandler.START_SEASON,
            {"season_id": "S01"},
            "lgm@test.com",
        )
        router.route_message(
            LeagueHandler.ASSIGNMENT_TABLE,
            {
                "assignments": [
                    {"role": "player1", "email": "me@test.com",
                     "game_id": "0101001", "group_id": "G1"},
                    {"role": "referee", "email": "ref@test.com",
                     "game_id": "0101001", "group_id": "G1"},
                    {"role": "player2", "email": "opp@test.com",
                     "game_id": "0101001", "group_id": "G1"},
                ],
            },
            "lgm@test.com",
        )
        # Start round 1
        result = router.route_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        assert len(result.games_to_run) == 1
        assert len(result.match_reports) == 0
        # Add round 2 assignments
        router.route_message(
            LeagueHandler.ASSIGNMENT_TABLE,
            {
                "assignments": [
                    {"role": "player1", "email": "me@test.com",
                     "game_id": "0102001", "group_id": "G2"},
                    {"role": "referee", "email": "ref2@test.com",
                     "game_id": "0102001", "group_id": "G2"},
                    {"role": "player2", "email": "opp2@test.com",
                     "game_id": "0102001", "group_id": "G2"},
                ],
            },
            "lgm@test.com",
        )
        # Start round 2 -- round 1 game terminated
        result = router.route_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 2},
            "lgm@test.com",
        )
        assert len(result.match_reports) == 1


class TestRouterQ21Completion:
    def test_score_feedback_populates_match_reports(self):
        router = MessageRouter(
            player_email="me@test.com", player_name="T",
            player_ai=_make_mock_ai(),
        )
        router.route_message(
            LeagueHandler.START_SEASON, {"season_id": "S01"}, "lgm@test.com",
        )
        router.route_message(
            LeagueHandler.ASSIGNMENT_TABLE,
            {"assignments": [
                {"role": "player1", "email": "me@test.com",
                 "game_id": "0101001", "group_id": "G1"},
                {"role": "referee", "email": "ref@test.com",
                 "game_id": "0101001", "group_id": "G1"},
                {"role": "player2", "email": "opp@test.com",
                 "game_id": "0101001", "group_id": "G1"},
            ]},
            "lgm@test.com",
        )
        router.route_message(
            LeagueHandler.NEW_ROUND, {"round_number": 1}, "lgm@test.com",
        )
        result = router.route_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": "0101001", "league_points": 85,
             "private_score": 0.9, "breakdown": {}},
            "ref@test.com",
        )
        assert len(result.match_reports) == 1
        assert result.match_reports[0]["status"] == "COMPLETED"
