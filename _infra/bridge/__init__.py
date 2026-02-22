# Area: Bridge (Gmail to RLGM Integration)
# PRD: docs/prd-rlgm.md
"""Bridge package - connects Gmail transport to MessageRouter."""
from _infra.bridge.email_parser import ParsedEmail, parse_gmail_message, normalize_msg_type
from _infra.bridge.response_sender import build_subject, send_routing_result
from _infra.bridge.scan_loop import ScanStats, scan_once, watch

__all__ = [
    "ParsedEmail", "parse_gmail_message", "normalize_msg_type",
    "build_subject", "send_routing_result",
    "ScanStats", "scan_once", "watch",
]
