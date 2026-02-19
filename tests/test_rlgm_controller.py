# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Tests for RLGMController with RoundLifecycleManager integration."""
import pytest
from unittest.mock import MagicMock
from _infra.rlgm.controller import RLGMController
from _infra.rlgm.league_handler import LeagueHandler
from _infra.gmc.q21_handler import Q21Handler
from _infra.rlgm.termination import GamePhase


def _make_mock_ai():
    ai = MagicMock()
    ai.get_warmup_answer.return_value = {"answer": "42"}
    ai.get_questions.return_value = {"questions": [{"q": "test"}]}
    ai.get_guess.return_value = {
        "opening_sentence": "It was dark.",
        "sentence_justification": "x " * 35,
        "associative_word": "dark",
        "word_justification": "x " * 35,
        "confidence": 0.8,
    }
    ai.on_score_received.return_value = None
    return ai


def _setup_controller_with_assignments():
    """Create an RLGMController with season started and assignments."""
    ctrl = RLGMController(
        player_email="me@test.com",
        player_name="Test",
        player_ai=_make_mock_ai(),
    )
    # Start season
    ctrl.process_message(
        LeagueHandler.START_SEASON,
        {"season_id": "S01"},
        "lgm@test.com",
    )
    # Two games in round 1, one game in round 2
    assignments_payload = {
        "assignments": [
            {"role": "player1", "email": "me@test.com",
             "game_id": "0101001", "group_id": "G1"},
            {"role": "referee", "email": "ref@test.com",
             "game_id": "0101001", "group_id": "G1"},
            {"role": "player2", "email": "opp@test.com",
             "game_id": "0101001", "group_id": "G1"},
            {"role": "player1", "email": "me@test.com",
             "game_id": "0101002", "group_id": "G2"},
            {"role": "referee", "email": "ref2@test.com",
             "game_id": "0101002", "group_id": "G2"},
            {"role": "player2", "email": "opp2@test.com",
             "game_id": "0101002", "group_id": "G2"},
            {"role": "player1", "email": "me@test.com",
             "game_id": "0102001", "group_id": "G3"},
            {"role": "referee", "email": "ref3@test.com",
             "game_id": "0102001", "group_id": "G3"},
            {"role": "player2", "email": "opp3@test.com",
             "game_id": "0102001", "group_id": "G3"},
        ],
    }
    ctrl.process_message(
        LeagueHandler.ASSIGNMENT_TABLE,
        assignments_payload,
        "lgm@test.com",
    )
    return ctrl


class TestNewRoundStartsGames:
    def test_new_round_returns_gprms(self):
        ctrl = _setup_controller_with_assignments()
        response, games, reports = ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        assert len(games) == 2
        assert len(reports) == 0  # No prior round

    def test_new_round_stops_previous_round(self):
        ctrl = _setup_controller_with_assignments()
        ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        # Round 2 should stop round 1 games
        response, games, reports = ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 2},
            "lgm@test.com",
        )
        assert len(reports) == 2  # Two round-1 games terminated
        assert len(games) == 1   # One round-2 game started


class TestQ21MessageRouting:
    def test_q21_routes_to_correct_game(self):
        ctrl = _setup_controller_with_assignments()
        ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        response = ctrl.process_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "0101001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is not None
        assert response["message_type"] == Q21Handler.WARMUP_RESPONSE

    def test_q21_stale_message_returns_none(self):
        ctrl = _setup_controller_with_assignments()
        ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        response = ctrl.process_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "STALE", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is None


class TestLeagueCompleted:
    def test_league_completed_stops_round(self):
        ctrl = _setup_controller_with_assignments()
        _, games, _ = ctrl.process_message(
            LeagueHandler.NEW_ROUND,
            {"round_number": 1},
            "lgm@test.com",
        )
        assert len(games) == 2
        response, _, reports = ctrl.process_message(
            LeagueHandler.LEAGUE_COMPLETED,
            {"final_standings": []},
            "lgm@test.com",
        )
        assert len(reports) == 2  # Both round-1 games terminated
