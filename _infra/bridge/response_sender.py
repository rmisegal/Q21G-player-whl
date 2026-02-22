# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Response sender - converts RoutingResult into outgoing Gmail emails."""
import uuid

from _infra.router import RoutingResult
from _infra.shared.logging.protocol_logger import log_sent, log_error


def build_subject(protocol: str, player_email: str, msg_type: str) -> str:
    """Build protocol subject line for an outgoing message."""
    txn_id = str(uuid.uuid4())
    return f"{protocol}::PLAYER::{player_email}::{txn_id}::{msg_type}"


def send_routing_result(
    result: RoutingResult,
    sender,
    player_email: str,
    manager_email: str,
) -> int:
    """Send all outgoing messages from a RoutingResult. Returns count sent."""
    sent = 0

    if result.response:
        resp = result.response
        msg_type = resp["message_type"]
        protocol = "Q21G.v1" if msg_type.upper().startswith("Q21") else "league.v2"
        subject = build_subject(protocol, player_email, msg_type)
        try:
            sender.send(
                to=resp["recipient"], subject=subject,
                body="", attachment={"payload": resp["payload"]},
            )
            log_sent(msg_type, resp["recipient"])
            sent += 1
        except Exception as e:
            log_error(f"Failed to send {msg_type}: {e}")

    for report in result.match_reports:
        rpt_type = report.get("message_type", "MATCH_RESULT_REPORT")
        subject = build_subject("league.v2", player_email, rpt_type)
        try:
            sender.send(
                to=manager_email, subject=subject,
                body="", attachment={"payload": report},
            )
            log_sent(rpt_type, manager_email)
            sent += 1
        except Exception as e:
            log_error(f"Failed to send {rpt_type}: {e}")

    return sent
