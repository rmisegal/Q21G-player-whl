# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Tests for RoundLifecycleManager."""
import pytest
from unittest.mock import MagicMock
from _infra.rlgm.round_lifecycle import RoundLifecycleManager
from _infra.rlgm.termination import GamePhase
from _infra.gmc.q21_handler import Q21Handler


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


def _make_assignments(round_number, count=2):
    """Create test assignments for a round."""
    return [
        {
            "game_id": f"01{round_number:02d}{i+1:03d}",
            "match_id": f"01{round_number:02d}{i+1:03d}",
            "round_number": round_number,
            "referee_email": f"ref{i+1}@test.com",
            "opponent_email": f"opp{i+1}@test.com",
            "my_role": "PLAYER1",
            "group_id": f"G{i+1}",
        }
        for i in range(count)
    ]


class TestStartRound:
    def test_start_round_creates_controllers(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        assignments = _make_assignments(1, count=3)
        lm.set_assignments(1, assignments)
        lm.start_round(1)
        assert len(lm.get_active_match_ids()) == 3
        assert lm.current_round == 1

    def test_start_round_with_no_assignments(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.start_round(1)
        assert len(lm.get_active_match_ids()) == 0

    def test_get_game_returns_controller(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        gmc = lm.get_game(match_id)
        assert gmc is not None
        assert gmc.phase == GamePhase.INITIALIZED

    def test_get_game_unknown_returns_none(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        assert lm.get_game("NONEXISTENT") is None


class TestStopRound:
    def test_stop_returns_reports_for_incomplete_games(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        lm.start_round(1)
        reports = lm.stop_current_round("NEW_ROUND_STARTED")
        assert len(reports) == 2
        assert all(r.reason == "NEW_ROUND_STARTED" for r in reports)
        assert all(r.phase_at_termination == "INITIALIZED" for r in reports)
        assert len(lm.get_active_match_ids()) == 0

    def test_stop_skips_completed_games(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        # Drive game to COMPLETED
        gmc = lm.get_game(match_id)
        gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 50, "private_score": 0.5, "breakdown": {}},
            "ref@test.com",
        )
        reports = lm.stop_current_round("NEW_ROUND_STARTED")
        assert len(reports) == 0  # Completed game produces no report

    def test_start_round_auto_stops_previous(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        lm.set_assignments(2, _make_assignments(2, count=1))
        gprms, reports = lm.start_round(1)
        assert len(reports) == 0  # No previous round
        gprms, reports = lm.start_round(2)
        assert len(reports) == 2  # Round 1 games force-stopped
        assert len(lm.get_active_match_ids()) == 1  # Round 2 game active

    def test_stop_empty_round_returns_empty(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        reports = lm.stop_current_round("NEW_ROUND_STARTED")
        assert reports == []


class TestRouteQ21Message:
    def test_route_to_correct_controller(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        lm.start_round(1)
        match_ids = lm.get_active_match_ids()
        response, reports = lm.route_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": match_ids[0], "warmup_question": "2+2"},
            "ref1@test.com",
        )
        assert response is not None
        assert response["message_type"] == Q21Handler.WARMUP_RESPONSE
        # First game advanced, second still INITIALIZED
        assert lm.get_game(match_ids[0]).phase == GamePhase.WARMUP_COMPLETE
        assert lm.get_game(match_ids[1]).phase == GamePhase.INITIALIZED

    def test_route_unknown_match_id_returns_none(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        response, reports = lm.route_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "NONEXISTENT", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert response is None
        assert reports == []


class TestCompletionReports:
    def test_route_score_feedback_returns_completion_report(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        response, reports = lm.route_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 85,
             "private_score": 0.9, "breakdown": {}},
            "ref1@test.com",
        )
        assert response is None  # SCORE_FEEDBACK has no response
        assert len(reports) == 1
        assert reports[0].status == "COMPLETED"
        assert reports[0].league_points == 85

    def test_route_non_terminal_returns_no_report(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        response, reports = lm.route_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": match_id, "warmup_question": "2+2"},
            "ref1@test.com",
        )
        assert response is not None
        assert len(reports) == 0


    def test_duplicate_score_feedback_ignored(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        # First SCORE_FEEDBACK → completion report
        _, reports1 = lm.route_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 85,
             "private_score": 0.9, "breakdown": {}},
            "ref1@test.com",
        )
        assert len(reports1) == 1
        # Duplicate SCORE_FEEDBACK → ignored, no extra report
        response, reports2 = lm.route_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 85,
             "private_score": 0.9, "breakdown": {}},
            "ref1@test.com",
        )
        assert response is None
        assert len(reports2) == 0


class TestHasAssignments:
    def test_has_assignments_true(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=2))
        assert lm.has_assignments_for_round(1) is True

    def test_has_assignments_false(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        assert lm.has_assignments_for_round(1) is False


class TestIsRoundComplete:
    def test_not_complete_when_games_active(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        assert lm.is_round_complete() is False

    def test_complete_when_all_games_done(self):
        lm = RoundLifecycleManager(player_ai=_make_mock_ai(), season_id="S01")
        lm.set_assignments(1, _make_assignments(1, count=1))
        lm.start_round(1)
        match_id = lm.get_active_match_ids()[0]
        gmc = lm.get_game(match_id)
        gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": match_id, "league_points": 50, "private_score": 0.5, "breakdown": {}},
            "ref@test.com",
        )
        assert lm.is_round_complete() is True
