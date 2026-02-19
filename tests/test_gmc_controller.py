# Area: GMC (Game Manager Component)
# PRD: docs/prd-rlgm.md
"""Tests for GMController phase tracking and termination reports."""
import pytest
from unittest.mock import MagicMock
from _infra.gmc.controller import GMController
from _infra.gmc.q21_handler import Q21Handler
from _infra.rlgm.termination import GamePhase


def _make_mock_ai():
    """Create a mock PlayerAI that returns valid responses."""
    ai = MagicMock()
    ai.get_warmup_answer.return_value = {"answer": "42"}
    ai.get_questions.return_value = {"questions": [{"q": "test"}]}
    ai.get_guess.return_value = {
        "opening_sentence": "It was a dark night.",
        "sentence_justification": "x " * 35,
        "associative_word": "darkness",
        "word_justification": "x " * 35,
        "confidence": 0.8,
    }
    ai.on_score_received.return_value = None
    return ai


class TestGMControllerPhases:
    def test_initial_phase_is_initialized(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        assert gmc.phase == GamePhase.INITIALIZED

    def test_warmup_transitions_to_warmup_complete(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.WARMUP_COMPLETE

    def test_round_start_transitions_to_questions_sent(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.ROUND_START,
            {"match_id": "M001", "book_name": "Test", "book_hint": "hint", "association_word": "color"},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.QUESTIONS_SENT

    def test_answers_transitions_to_guess_submitted(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.ANSWERS_BATCH,
            {"match_id": "M001", "answers": [{"question_number": 1, "answer": "A"}]},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.GUESS_SUBMITTED

    def test_score_transitions_to_completed(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        result = gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": "M001", "league_points": 85, "private_score": 0.9, "breakdown": {}},
            "ref@test.com",
        )
        assert gmc.phase == GamePhase.COMPLETED
        assert result is None  # Score feedback is terminal


class TestGMControllerMessageTracking:
    def test_last_sent_after_warmup(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        assert gmc.last_sent == Q21Handler.WARMUP_RESPONSE
        assert gmc.last_received == Q21Handler.WARMUP_CALL

    def test_last_sent_after_questions(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.ROUND_START,
            {"match_id": "M001", "book_name": "T", "book_hint": "h", "association_word": "w"},
            "ref@test.com",
        )
        assert gmc.last_sent == Q21Handler.QUESTIONS_BATCH
        assert gmc.last_received == Q21Handler.ROUND_START


class TestGMControllerTermination:
    def test_get_match_report_terminated(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        report = gmc.get_match_report("NEW_ROUND_STARTED")
        assert report.status == "TERMINATED"
        assert report.match_id == "M001"
        assert report.game_id == "0102001"
        assert report.round_number == 2
        assert report.season_id == "S01"
        assert report.phase_at_termination == "WARMUP_COMPLETE"
        assert report.last_actor == "PLAYER"
        assert report.last_message_sent == Q21Handler.WARMUP_RESPONSE
        assert report.last_message_received == Q21Handler.WARMUP_CALL
        assert report.reason == "NEW_ROUND_STARTED"

    def test_terminate_sets_phase(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.terminate()
        assert gmc.phase == GamePhase.TERMINATED

    def test_match_report_initialized_phase(self):
        """INITIALIZED: last_actor is NONE (nobody acted yet)."""
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        report = gmc.get_match_report("NEW_ROUND_STARTED")
        assert report.status == "TERMINATED"
        assert report.last_actor == "NONE"
        assert report.last_message_sent == ""
        assert report.last_message_received == ""


class TestGMControllerCompletionReport:
    def test_completion_report_after_score(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.SCORE_FEEDBACK,
            {"match_id": "M001", "league_points": 85,
             "private_score": 0.9, "breakdown": {"accuracy": 0.95}},
            "ref@test.com",
        )
        report = gmc.get_match_report("GAME_COMPLETED")
        assert report.status == "COMPLETED"
        assert report.league_points == 85
        assert report.private_score == 0.9
        assert report.breakdown == {"accuracy": 0.95}
        assert report.phase_at_termination == "COMPLETED"

    def test_incomplete_report_has_no_scores(self):
        gmc = GMController(player_ai=_make_mock_ai())
        gmc.initialize("M001", "0102001", 2, "S01", "ref@test.com")
        gmc.handle_q21_message(
            Q21Handler.WARMUP_CALL,
            {"match_id": "M001", "warmup_question": "2+2"},
            "ref@test.com",
        )
        report = gmc.get_match_report("NEW_ROUND_STARTED")
        assert report.status == "TERMINATED"
        assert report.league_points is None
        assert report.private_score is None
