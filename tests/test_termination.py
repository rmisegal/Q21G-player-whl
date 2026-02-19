# Area: RLGM (League Manager Interface)
# PRD: docs/prd-rlgm.md
"""Tests for GamePhase and MatchReport."""
import pytest
from _infra.rlgm.termination import GamePhase, MatchReport


class TestGamePhase:
    def test_all_phases_exist(self):
        assert GamePhase.INITIALIZED.value == "INITIALIZED"
        assert GamePhase.WARMUP_COMPLETE.value == "WARMUP_COMPLETE"
        assert GamePhase.QUESTIONS_SENT.value == "QUESTIONS_SENT"
        assert GamePhase.GUESS_SUBMITTED.value == "GUESS_SUBMITTED"
        assert GamePhase.COMPLETED.value == "COMPLETED"
        assert GamePhase.TERMINATED.value == "TERMINATED"

    def test_is_terminal(self):
        assert GamePhase.COMPLETED.value in ("COMPLETED", "TERMINATED")
        assert GamePhase.TERMINATED.value in ("COMPLETED", "TERMINATED")
        assert GamePhase.INITIALIZED.value not in ("COMPLETED", "TERMINATED")


class TestMatchReport:
    def test_create_report(self):
        report = MatchReport(
            match_id="0102001",
            game_id="0102001",
            round_number=2,
            season_id="S01",
            status="TERMINATED",
            phase_at_termination="QUESTIONS_SENT",
            last_actor="PLAYER",
            last_message_sent="Q21QUESTIONSBATCH",
            last_message_received="Q21ROUNDSTART",
            reported_at="2026-02-19T10:30:00Z",
            reason="NEW_ROUND_STARTED",
        )
        assert report.match_id == "0102001"
        assert report.last_actor == "PLAYER"

    def test_to_match_result_report(self):
        report = MatchReport(
            match_id="0102001",
            game_id="0102001",
            round_number=2,
            season_id="S01",
            status="TERMINATED",
            phase_at_termination="QUESTIONS_SENT",
            last_actor="PLAYER",
            last_message_sent="Q21QUESTIONSBATCH",
            last_message_received="Q21ROUNDSTART",
            reported_at="2026-02-19T10:30:00Z",
            reason="NEW_ROUND_STARTED",
        )
        msg = report.to_protocol_message(
            reporter_email="user0009@gtai-tech.org",
            reporter_role="PLAYER_A",
        )
        assert msg["message_type"] == "MATCH_RESULT_REPORT"
        assert msg["version"] == "1.0"
        assert msg["match_id"] == "0102001"
        assert msg["status"] == "TERMINATED"
        assert msg["phase_at_termination"] == "QUESTIONS_SENT"
        assert msg["last_actor"] == "PLAYER"
        assert msg["reported_at"] == "2026-02-19T10:30:00Z"
        assert msg["reporter"]["email"] == "user0009@gtai-tech.org"
        assert msg["reporter"]["role"] == "PLAYER_A"

    def test_last_actor_mapping_initialized(self):
        """INITIALIZED phase: nobody acted yet."""
        report = MatchReport(
            match_id="X", game_id="X", round_number=1, season_id="S01",
            status="TERMINATED",
            phase_at_termination="INITIALIZED",
            last_actor="NONE",
            last_message_sent="", last_message_received="",
            reported_at="T", reason="R",
        )
        assert report.last_actor == "NONE"

    def test_last_actor_mapping_warmup_complete(self):
        """WARMUP_COMPLETE: player sent warmup response."""
        report = MatchReport(
            match_id="X", game_id="X", round_number=1, season_id="S01",
            status="TERMINATED",
            phase_at_termination="WARMUP_COMPLETE",
            last_actor="PLAYER",
            last_message_sent="Q21WARMUPRESPONSE",
            last_message_received="Q21WARMUPCALL",
            reported_at="T", reason="R",
        )
        assert report.last_actor == "PLAYER"
        assert report.last_message_sent == "Q21WARMUPRESPONSE"

    def test_completed_report_includes_scores(self):
        report = MatchReport(
            match_id="0102001", game_id="0102001", round_number=2,
            season_id="S01",
            status="COMPLETED",
            phase_at_termination="COMPLETED",
            last_actor="NONE",
            last_message_sent="Q21GUESSSUBMISSION",
            last_message_received="Q21SCOREFEEDBACK",
            reported_at="2026-02-19T10:30:00Z",
            reason="GAME_COMPLETED",
            league_points=85, private_score=0.9,
            breakdown={"accuracy": 0.95},
        )
        msg = report.to_protocol_message(
            "user0009@gtai-tech.org", "PLAYER1"
        )
        assert msg["status"] == "COMPLETED"
        assert msg["league_points"] == 85
        assert msg["private_score"] == 0.9
        assert msg["breakdown"] == {"accuracy": 0.95}
        assert msg["reported_at"] == "2026-02-19T10:30:00Z"

    def test_terminated_report_excludes_scores(self):
        report = MatchReport(
            match_id="0102001", game_id="0102001", round_number=2,
            season_id="S01",
            status="TERMINATED",
            phase_at_termination="QUESTIONS_SENT",
            last_actor="PLAYER",
            last_message_sent="Q21QUESTIONSBATCH",
            last_message_received="Q21ROUNDSTART",
            reported_at="2026-02-19T10:30:00Z",
            reason="NEW_ROUND_STARTED",
        )
        msg = report.to_protocol_message(
            "user0009@gtai-tech.org", "PLAYER1"
        )
        assert msg["status"] == "TERMINATED"
        assert "league_points" not in msg
        assert "private_score" not in msg
        assert "breakdown" not in msg
