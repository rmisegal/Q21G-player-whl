# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Tests for scan_loop module."""
import sys
import pytest
from unittest.mock import MagicMock, patch, call

# Mock q21_player whl package before importing scan_loop
_mock_gmail_utils = MagicMock()
for mod in [
    "q21_player", "q21_player._infra", "q21_player._infra.cli",
    "q21_player._infra.cli.gmail_utils",
]:
    sys.modules.setdefault(mod, MagicMock())
sys.modules["q21_player._infra.cli.gmail_utils"] = _mock_gmail_utils

from _infra.bridge.scan_loop import scan_once, _set_log_context, SEASON_MESSAGES
from _infra.router import MessageRouter, RoutingResult


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


def _mock_get_header(msg, name):
    """Extract header from mock Gmail message."""
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"] == name:
            return h["value"]
    return ""


class TestSetLogContext:
    @patch("_infra.bridge.scan_loop.set_season_context")
    def test_season_message_sets_season_context(self, mock_ctx):
        router = MagicMock()
        _set_log_context("BROADCAST_START_SEASON", "", {}, router)
        mock_ctx.assert_called_once()

    @patch("_infra.bridge.scan_loop.set_round_context")
    def test_round_message_sets_round_context(self, mock_ctx):
        router = MagicMock()
        lifecycle = MagicMock()
        lifecycle.has_assignments_for_round.return_value = True
        router.get_rlgm.return_value.get_lifecycle.return_value = lifecycle
        _set_log_context("BROADCAST_NEW_LEAGUE_ROUND", "", {"round_number": 2}, router)
        mock_ctx.assert_called_once_with(2, True)

    @patch("_infra.bridge.scan_loop.set_game_context")
    def test_q21_message_sets_game_context(self, mock_ctx):
        router = MagicMock()
        _set_log_context("Q21WARMUPCALL", "0101001", {}, router)
        mock_ctx.assert_called_once_with("0101001", True)


class TestScanOnce:
    def test_processes_messages_oldest_first(self):
        client = MagicMock()
        sender = MagicMock()
        router = MessageRouter(player_email="me@test.com", player_name="T", player_ai=_make_mock_ai())

        client.list_messages.return_value = {
            "messages": [{"id": "msg2"}, {"id": "msg1"}]
        }

        def mock_get(msg_id):
            subjects = {
                "msg1": "league.v2::LGM::lgm@t.com::tx1::BROADCAST_START_SEASON",
                "msg2": "league.v2::LGM::lgm@t.com::tx2::BROADCAST_START_SEASON",
            }
            return {"id": msg_id, "payload": {"headers": [{"name": "Subject", "value": subjects[msg_id]}]}}
        client.get_message.side_effect = mock_get

        _mock_gmail_utils.get_header.side_effect = _mock_get_header
        _mock_gmail_utils.get_payload.return_value = {"payload": {"season_id": "S01"}}

        stats = scan_once(client, sender, router, "lgm@t.com")

        assert stats.found == 2
        assert stats.processed == 2
        get_calls = client.get_message.call_args_list
        assert get_calls[0] == call("msg1")
        assert get_calls[1] == call("msg2")

    def test_skips_invalid_subjects(self):
        client = MagicMock()
        sender = MagicMock()
        router = MessageRouter(player_email="me@test.com", player_name="T", player_ai=_make_mock_ai())
        client.list_messages.return_value = {"messages": [{"id": "msg1"}]}
        client.get_message.return_value = {
            "id": "msg1",
            "payload": {"headers": [{"name": "Subject", "value": "garbage"}]},
        }
        _mock_gmail_utils.get_header.side_effect = _mock_get_header
        _mock_gmail_utils.get_payload.return_value = None

        stats = scan_once(client, sender, router, "lgm@t.com")
        assert stats.skipped == 1
        assert stats.processed == 0

    def test_empty_inbox(self):
        client = MagicMock()
        sender = MagicMock()
        router = MessageRouter(player_email="me@test.com", player_name="T", player_ai=_make_mock_ai())
        client.list_messages.return_value = {"messages": []}
        stats = scan_once(client, sender, router, "lgm@t.com")
        assert stats.found == 0
