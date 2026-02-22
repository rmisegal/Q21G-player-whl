# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Scan loop - wires Gmail transport to MessageRouter."""
import time
from dataclasses import dataclass, field
from typing import List

from _infra.router import MessageRouter
from _infra.bridge.email_parser import parse_gmail_message
from _infra.bridge.response_sender import send_routing_result
from _infra.shared.logging.protocol_logger import (
    set_season_context, set_round_context, set_game_context,
    log_received, log_error,
)

GMAIL_QUERY = "(subject:league.v2 OR subject:Q21G.v1) is:unread"
SEASON_MESSAGES = {
    "BROADCAST_START_SEASON", "SEASON_REGISTRATION_RESPONSE",
    "BROADCAST_ASSIGNMENT_TABLE", "LEAGUE_COMPLETED",
}


@dataclass
class ScanStats:
    """Statistics from a single scan pass."""
    found: int = 0
    processed: int = 0
    skipped: int = 0
    sent: int = 0
    errors: List[str] = field(default_factory=list)


def _set_log_context(
    msg_type: str, game_id: str, payload: dict, router: MessageRouter,
) -> None:
    """Set protocol logger context based on message type."""
    if msg_type in SEASON_MESSAGES:
        set_season_context()
    elif msg_type == "BROADCAST_NEW_LEAGUE_ROUND":
        rn = payload.get("round_number", 1)
        lifecycle = router.get_rlgm().get_lifecycle()
        active = lifecycle.has_assignments_for_round(rn)
        set_round_context(rn, active)
    elif msg_type.upper().startswith("Q21"):
        set_game_context(game_id, True)


def scan_once(client, sender, router, manager_email, max_messages=20):
    """Scan Gmail inbox once. Returns ScanStats."""
    from q21_player._infra.cli.gmail_utils import get_header, get_payload

    stats = ScanStats()
    try:
        msgs = client.list_messages(query=GMAIL_QUERY, max_results=max_messages)
        refs = msgs.get("messages", [])
    except Exception as e:
        log_error(f"Failed to list messages: {e}")
        stats.errors.append(str(e))
        return stats

    stats.found = len(refs)
    player_email = router.get_rlgm().player_email

    for msg_ref in reversed(refs):  # Oldest first
        msg_id = msg_ref["id"]
        try:
            msg = client.get_message(msg_id)
            subject = get_header(msg, "Subject")
            payload_data = get_payload(client, msg)

            parsed = parse_gmail_message(subject, payload_data)
            if parsed is None:
                stats.skipped += 1
                client.modify_message(msg_id, remove_labels=["UNREAD"])
                continue

            _set_log_context(parsed.msg_type, parsed.game_id, parsed.payload, router)
            log_received(parsed.msg_type, parsed.sender, parsed.deadline)

            result = router.route_message(parsed.msg_type, parsed.payload, parsed.sender)
            if result.handled:
                stats.sent += send_routing_result(
                    result, sender, player_email, manager_email,
                )

            client.modify_message(msg_id, remove_labels=["UNREAD"])
            stats.processed += 1
        except Exception as e:
            log_error(f"Failed to process {msg_id[:8]}: {e}")
            stats.errors.append(f"{msg_id[:8]}: {e}")

    return stats


def watch(client, sender, router, manager_email, poll_interval=30, max_messages=20):
    """Continuously poll Gmail for protocol messages."""
    print(f"[Watch] Polling every {poll_interval}s. Ctrl+C to stop.")
    try:
        while True:
            scan_once(client, sender, router, manager_email, max_messages)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[Watch] Stopped.")
