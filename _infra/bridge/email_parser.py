# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Email parser - extracts protocol fields from Gmail messages."""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ParsedEmail:
    """Parsed protocol email fields."""
    msg_type: str
    payload: dict
    sender: str
    game_id: str
    deadline: str
    protocol: str
    raw_msg_type: str


def normalize_msg_type(msg_type: str) -> str:
    """Normalize message type. Strips underscores from Q21 types only."""
    upper = msg_type.upper()
    if upper.startswith("Q21") and "_" in upper:
        return upper.replace("_", "")
    return msg_type


def parse_gmail_message(
    subject: str,
    payload_data: Optional[dict[str, Any]],
) -> Optional[ParsedEmail]:
    """Parse Gmail subject + payload into protocol fields.

    Subject format: protocol::role::sender::txid::msg_type

    Returns None if subject has fewer than 5 '::'-delimited parts.
    """
    parts = subject.split("::")
    if len(parts) < 5:
        return None

    raw_msg_type = parts[4]
    msg_type = normalize_msg_type(raw_msg_type)

    # Unwrap {"payload": {...}} -> inner dict; pass through if no wrapper
    inner: dict = {}
    if payload_data:
        inner = payload_data.get("payload", payload_data)

    game_id = (
        inner.get("game_id") or inner.get("match_id")
        or (payload_data or {}).get("game_id")
        or (payload_data or {}).get("match_id")
        or ""
    )
    deadline = inner.get("deadline") or (payload_data or {}).get("deadline", "")

    return ParsedEmail(
        msg_type=msg_type,
        payload=inner,
        sender=parts[2],
        game_id=game_id,
        deadline=deadline,
        protocol=parts[0],
        raw_msg_type=raw_msg_type,
    )
