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


def _game_group(gid, group, ref="ref@test.com", opp="opp@test.com"):
    """Build a 3-row assignment group (player1, referee, player2)."""
    return [
        {"role": "player1", "email": "me@test.com",
         "game_id": gid, "group_id": group},
        {"role": "referee", "email": ref,
         "game_id": gid, "group_id": group},
        {"role": "player2", "email": opp,
         "game_id": gid, "group_id": group},
    ]


def _setup_controller_with_assignments():
    """Create an RLGMController with season started and assignments."""
    ctrl = RLGMController(
        player_email="me@test.com", player_name="Test",
        player_ai=_make_mock_ai(),
    )
    ctrl.process_message(
        LeagueHandler.START_SEASON, {"season_id": "S01"}, "lgm@test.com",
    )
    assignments = (
        _game_group("0101001", "G1") +
        _game_group("0101002", "G2", "ref2@test.com", "opp2@test.com") +
        _game_group("0102001", "G3", "ref3@test.com", "opp3@test.com")
    )
    ctrl.process_message(
        LeagueHandler.ASSIGNMENT_TABLE,
        {"assignments": assignments},
        "lgm@test.com",
    )
    return ctrl


def _start_round(ctrl, round_number):
    return ctrl.process_message(
        LeagueHandler.NEW_ROUND, {"round_number": round_number}, "lgm@test.com",
    )


class TestNewRoundStartsGames:
    def test_new_round_returns_gprms(self):
        ctrl = _setup_controller_with_assignments()
        _, games, reports = _start_round(ctrl, 1)
        assert len(games) == 2
        assert len(reports) == 0

    def test_new_round_stops_previous_round(self):
        ctrl = _setup_controller_with_assignments()
        _start_round(ctrl, 1)
        _, games, reports = _start_round(ctrl, 2)
        assert len(reports) == 2  # Two round-1 games terminated
        assert len(games) == 1   # One round-2 game started


class TestQ21MessageRouting:
    def test_q21_routes_to_correct_game(self):
        ctrl = _setup_controller_with_assignments()
        _start_round(ctrl, 1)
        response, reports = ctrl.process_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "0101001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is not None
        assert response["message_type"] == Q21Handler.WARMUP_RESPONSE
        assert reports == []

    def test_q21_stale_message_returns_none(self):
        ctrl = _setup_controller_with_assignments()
        _start_round(ctrl, 1)
        response, reports = ctrl.process_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "STALE", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is None
        assert reports == []


class TestQ21CompletionReport:
    def test_score_feedback_returns_completion_report(self):
        ctrl = _setup_controller_with_assignments()
        _start_round(ctrl, 1)
        response, reports = ctrl.process_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": "0101001", "league_points": 85,
             "private_score": 0.9, "breakdown": {}},
            "ref@test.com",
        )
        assert response is None
        assert len(reports) == 1
        assert reports[0].status == "COMPLETED"


class TestLeagueCompleted:
    def test_league_completed_stops_round(self):
        ctrl = _setup_controller_with_assignments()
        _, games, _ = _start_round(ctrl, 1)
        assert len(games) == 2
        _, _, reports = ctrl.process_message(
            LeagueHandler.LEAGUE_COMPLETED,
            {"final_standings": []},
            "lgm@test.com",
        )
        assert len(reports) == 2  # Both round-1 games terminated
