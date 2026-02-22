# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Tests for email_parser module."""
import pytest
from _infra.bridge.email_parser import parse_gmail_message, normalize_msg_type


class TestNormalizeMsgType:
    def test_q21_with_underscores(self):
        assert normalize_msg_type("Q21_WARMUP_CALL") == "Q21WARMUPCALL"

    def test_q21_without_underscores(self):
        assert normalize_msg_type("Q21WARMUPCALL") == "Q21WARMUPCALL"

    def test_league_type_unchanged(self):
        assert normalize_msg_type("BROADCAST_START_SEASON") == "BROADCAST_START_SEASON"

    def test_q21_round_start(self):
        assert normalize_msg_type("Q21_ROUND_START") == "Q21ROUNDSTART"

    def test_q21_answers_batch(self):
        assert normalize_msg_type("Q21_ANSWERS_BATCH") == "Q21ANSWERSBATCH"

    def test_q21_score_feedback(self):
        assert normalize_msg_type("Q21_SCORE_FEEDBACK") == "Q21SCOREFEEDBACK"


class TestParseGmailMessage:
    def test_valid_q21_subject(self):
        subject = "Q21G.v1::REFEREE::ref@test.com::tx123::Q21_WARMUP_CALL"
        payload = {"payload": {"match_id": "0101001", "warmup_question": "2+2"}}
        parsed = parse_gmail_message(subject, payload)
        assert parsed is not None
        assert parsed.msg_type == "Q21WARMUPCALL"
        assert parsed.sender == "ref@test.com"
        assert parsed.payload == {"match_id": "0101001", "warmup_question": "2+2"}
        assert parsed.game_id == "0101001"
        assert parsed.protocol == "Q21G.v1"

    def test_valid_league_subject(self):
        subject = "league.v2::LEAGUE_MANAGER::lgm@test.com::tx456::BROADCAST_START_SEASON"
        payload = {"payload": {"season_id": "S01"}}
        parsed = parse_gmail_message(subject, payload)
        assert parsed.msg_type == "BROADCAST_START_SEASON"
        assert parsed.sender == "lgm@test.com"
        assert parsed.payload == {"season_id": "S01"}

    def test_invalid_subject_too_few_parts(self):
        assert parse_gmail_message("not::enough::parts", None) is None

    def test_none_payload(self):
        subject = "Q21G.v1::REF::ref@t.com::tx::Q21WARMUPCALL"
        parsed = parse_gmail_message(subject, None)
        assert parsed is not None
        assert parsed.payload == {}
        assert parsed.game_id == ""

    def test_unwrapped_payload(self):
        """Payload without 'payload' key wrapping."""
        subject = "Q21G.v1::REF::ref@t.com::tx::Q21WARMUPCALL"
        payload = {"match_id": "0101001", "warmup_question": "2+2"}
        parsed = parse_gmail_message(subject, payload)
        assert parsed.payload == {"match_id": "0101001", "warmup_question": "2+2"}
        assert parsed.game_id == "0101001"

    def test_game_id_from_match_id(self):
        subject = "Q21G.v1::REF::ref@t.com::tx::Q21ANSWERSBATCH"
        payload = {"payload": {"match_id": "0102003", "answers": []}}
        parsed = parse_gmail_message(subject, payload)
        assert parsed.game_id == "0102003"

    def test_deadline_extraction(self):
        subject = "Q21G.v1::REF::ref@t.com::tx::Q21ROUNDSTART"
        payload = {"payload": {"match_id": "0101001", "deadline": "2026-02-22T19:10:00Z"}}
        parsed = parse_gmail_message(subject, payload)
        assert parsed.deadline == "2026-02-22T19:10:00Z"
