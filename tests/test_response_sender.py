# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Tests for response_sender module."""
import pytest
from unittest.mock import MagicMock
from _infra.bridge.response_sender import build_subject, send_routing_result
from _infra.router import RoutingResult


class TestBuildSubject:
    def test_q21_protocol(self):
        subj = build_subject("Q21G.v1", "me@test.com", "Q21WARMUPRESPONSE")
        parts = subj.split("::")
        assert parts[0] == "Q21G.v1"
        assert parts[1] == "PLAYER"
        assert parts[2] == "me@test.com"
        assert len(parts[3]) > 0  # UUID
        assert parts[4] == "Q21WARMUPRESPONSE"

    def test_league_protocol(self):
        subj = build_subject("league.v2", "me@test.com", "SEASON_REGISTRATION_REQUEST")
        parts = subj.split("::")
        assert parts[0] == "league.v2"
        assert parts[4] == "SEASON_REGISTRATION_REQUEST"


class TestSendRoutingResult:
    def test_sends_response(self):
        sender = MagicMock()
        result = RoutingResult(
            response={"message_type": "Q21WARMUPRESPONSE",
                       "payload": {"match_id": "0101001", "answer": "4"},
                       "recipient": "ref@test.com"},
            games_to_run=[], handled=True,
        )
        sent = send_routing_result(result, sender, "me@test.com", "lgm@test.com")
        assert sent == 1
        sender.send.assert_called_once()
        call_kwargs = sender.send.call_args
        assert call_kwargs.kwargs["to"] == "ref@test.com"
        assert "Q21WARMUPRESPONSE" in call_kwargs.kwargs["subject"]
        assert call_kwargs.kwargs["attachment"] == {"payload": {"match_id": "0101001", "answer": "4"}}

    def test_sends_match_reports(self):
        sender = MagicMock()
        result = RoutingResult(
            response=None, games_to_run=[], handled=True,
            match_reports=[{"message_type": "MATCH_RESULT_REPORT", "match_id": "0101001"}],
        )
        sent = send_routing_result(result, sender, "me@test.com", "lgm@test.com")
        assert sent == 1
        call_kwargs = sender.send.call_args
        assert call_kwargs.kwargs["to"] == "lgm@test.com"

    def test_no_response_no_reports(self):
        sender = MagicMock()
        result = RoutingResult(response=None, games_to_run=[], handled=True)
        sent = send_routing_result(result, sender, "me@test.com", "lgm@test.com")
        assert sent == 0
        sender.send.assert_not_called()

    def test_response_plus_reports(self):
        sender = MagicMock()
        result = RoutingResult(
            response={"message_type": "SEASON_REGISTRATION_REQUEST",
                       "payload": {"season_id": "S01"},
                       "recipient": "lgm@test.com"},
            games_to_run=[], handled=True,
            match_reports=[{"message_type": "MATCH_RESULT_REPORT"}],
        )
        sent = send_routing_result(result, sender, "me@test.com", "lgm@test.com")
        assert sent == 2
        assert sender.send.call_count == 2
