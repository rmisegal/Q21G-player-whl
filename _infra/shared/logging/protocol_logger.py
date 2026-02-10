"""Protocol Logger - Colored output for player protocol messages.

Implements the logging format from LOGGER_OUTPUT_PLAYER.md PRD.
"""
from datetime import datetime
from typing import Optional


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    ORANGE = "\033[93m"  # Using yellow/orange
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


# Message type to display name mapping (PRD Section 10)
MESSAGE_DISPLAY_NAMES = {
    # Messages player RECEIVES
    "BROADCAST_START_SEASON": "START-SEASON",
    "SEASON_REGISTRATION_RESPONSE": "SIGNUP-RESPONSE",
    "BROADCAST_ASSIGNMENT_TABLE": "ASSIGNMENT-TABLE",
    "BROADCAST_NEW_LEAGUE_ROUND": "START-ROUND",
    "Q21WARMUPCALL": "PING-CALL",
    "Q21_WARMUP_CALL": "PING-CALL",
    "Q21ROUNDSTART": "START-GAME",
    "Q21_ROUND_START": "START-GAME",
    "Q21ANSWERSBATCH": "QUESTION-ANSWERS",
    "Q21_ANSWERS_BATCH": "QUESTION-ANSWERS",
    "Q21SCOREFEEDBACK": "ROUND-SCORE-REPORT",
    "Q21_SCORE_FEEDBACK": "ROUND-SCORE-REPORT",
    "LEAGUE_COMPLETED": "SEASON-ENDED",
    # Messages player SENDS
    "SEASON_REGISTRATION_REQUEST": "SEASON-SIGNUP",
    "Q21WARMUPRESPONSE": "PING-RESPONSE",
    "Q21_WARMUP_RESPONSE": "PING-RESPONSE",
    "Q21QUESTIONSBATCH": "ASK-20-QUESTIONS",
    "Q21_QUESTIONS_BATCH": "ASK-20-QUESTIONS",
    "Q21GUESSSUBMISSION": "MY-GUESS",
    "Q21_GUESS_SUBMISSION": "MY-GUESS",
}

# Expected response mapping (PRD Section 10)
EXPECTED_RESPONSES = {
    "BROADCAST_START_SEASON": "SEASON-SIGNUP",
    "SEASON_REGISTRATION_REQUEST": "SIGNUP-RESPONSE",
    "SEASON_REGISTRATION_RESPONSE": "Wait for ASSIGNMENT-TABLE",
    "BROADCAST_ASSIGNMENT_TABLE": "Wait for START-ROUND",
    "BROADCAST_NEW_LEAGUE_ROUND": "Wait for PING-CALL",
    "Q21WARMUPCALL": "PING-RESPONSE",
    "Q21_WARMUP_CALL": "PING-RESPONSE",
    "Q21WARMUPRESPONSE": "Wait for START-GAME",
    "Q21_WARMUP_RESPONSE": "Wait for START-GAME",
    "Q21ROUNDSTART": "ASK-20-QUESTIONS",
    "Q21_ROUND_START": "ASK-20-QUESTIONS",
    "Q21QUESTIONSBATCH": "QUESTION-ANSWERS",
    "Q21_QUESTIONS_BATCH": "QUESTION-ANSWERS",
    "Q21ANSWERSBATCH": "MY-GUESS",
    "Q21_ANSWERS_BATCH": "MY-GUESS",
    "Q21GUESSSUBMISSION": "ROUND-SCORE-REPORT",
    "Q21_GUESS_SUBMISSION": "ROUND-SCORE-REPORT",
    "Q21SCOREFEEDBACK": "None (terminal)",
    "Q21_SCORE_FEEDBACK": "None (terminal)",
    "LEAGUE_COMPLETED": "None (terminal)",
}

# Callback display names
CALLBACK_DISPLAY_NAMES = {
    "get_warmup_answer": "answer_warmup",
    "get_questions": "generate_questions",
    "get_guess": "formulate_guess",
    "on_score_received": "receive_score",
}


class ProtocolLogger:
    """Logger for protocol messages with colored output."""

    _current_game_id: str = "0000000"
    _player_active: bool = True

    @classmethod
    def set_game_context(cls, game_id: str, player_active: bool = True) -> None:
        """Set current game context for logging."""
        cls._current_game_id = game_id or "0000000"
        cls._player_active = player_active

    @classmethod
    def _get_display_name(cls, msg_type: str) -> str:
        """Get display name for message type."""
        # Normalize: remove underscores and uppercase
        normalized = msg_type.replace("_", "").upper()
        # Try exact match first
        if msg_type in MESSAGE_DISPLAY_NAMES:
            return MESSAGE_DISPLAY_NAMES[msg_type]
        # Try normalized match
        for key, value in MESSAGE_DISPLAY_NAMES.items():
            if key.replace("_", "").upper() == normalized:
                return value
        return msg_type

    @classmethod
    def _get_expected_response(cls, msg_type: str) -> str:
        """Get expected response for message type."""
        normalized = msg_type.replace("_", "").upper()
        if msg_type in EXPECTED_RESPONSES:
            return EXPECTED_RESPONSES[msg_type]
        for key, value in EXPECTED_RESPONSES.items():
            if key.replace("_", "").upper() == normalized:
                return value
        return "Unknown"

    @classmethod
    def _get_role(cls) -> str:
        """Get current role status."""
        return "PLAYER-ACTIVE" if cls._player_active else "PLAYER-INACTIVE"

    @classmethod
    def _format_time(cls, with_ms: bool = False) -> str:
        """Format current time."""
        now = datetime.now()
        if with_ms:
            return now.strftime("%H:%M:%S:%f")[:-3]  # HH:MM:SS:MS
        return now.strftime("%H:%M:%S")

    @classmethod
    def _format_deadline(cls, deadline: Optional[str]) -> str:
        """Format deadline string."""
        if not deadline:
            return "--:--:--"
        try:
            # Try to parse ISO format
            dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            return dt.strftime("%H:%M:%S")
        except (ValueError, AttributeError):
            return deadline if deadline else "--:--:--"

    @classmethod
    def log_received(
        cls,
        msg_type: str,
        sender_email: str,
        game_id: Optional[str] = None,
        deadline: Optional[str] = None,
    ) -> None:
        """Log a received protocol message (GREEN)."""
        display_name = cls._get_display_name(msg_type)
        expected = cls._get_expected_response(msg_type)
        gid = game_id or cls._current_game_id
        role = cls._get_role()
        dl = cls._format_deadline(deadline)
        time_str = cls._format_time()

        line = (
            f"{Colors.GREEN}"
            f"{time_str} | GAME-ID: {gid} | RECEIVED | from {sender_email:<30} | "
            f"{display_name:<20} | EXPECTED-RESPONSE: {expected:<25} | "
            f"ROLE: {role} | DEADLINE: {dl}"
            f"{Colors.RESET}"
        )
        print(line)

    @classmethod
    def log_sent(
        cls,
        msg_type: str,
        recipient_email: str,
        game_id: Optional[str] = None,
        deadline: Optional[str] = None,
    ) -> None:
        """Log a sent protocol message (GREEN)."""
        display_name = cls._get_display_name(msg_type)
        expected = cls._get_expected_response(msg_type)
        gid = game_id or cls._current_game_id
        role = cls._get_role()
        dl = cls._format_deadline(deadline)
        time_str = cls._format_time()

        line = (
            f"{Colors.GREEN}"
            f"{time_str} | GAME-ID: {gid} | SENT     | to {recipient_email:<32} | "
            f"{display_name:<20} | EXPECTED-RESPONSE: {expected:<25} | "
            f"ROLE: {role} | DEADLINE: {dl}"
            f"{Colors.RESET}"
        )
        print(line)

    @classmethod
    def log_rejected(cls, msg_type: str, sender_email: str, reason: str = "") -> None:
        """Log a rejected message (RED)."""
        time_str = cls._format_time()
        display_name = cls._get_display_name(msg_type)
        msg = f"REJECTED {display_name} from {sender_email}"
        if reason:
            msg += f": {reason}"
        print(f"{Colors.RED}[ERROR] {time_str} | {msg}{Colors.RESET}")

    @classmethod
    def log_error(cls, message: str) -> None:
        """Log an error message (RED)."""
        time_str = cls._format_time()
        print(f"{Colors.RED}[ERROR] {time_str} | {message}{Colors.RESET}")

    @classmethod
    def log_callback_call(cls, callback_name: str) -> None:
        """Log callback invocation (ORANGE)."""
        display_name = CALLBACK_DISPLAY_NAMES.get(callback_name, callback_name)
        time_str = cls._format_time(with_ms=True)
        line = (
            f"{Colors.ORANGE}"
            f"{time_str} | CALLBACK: {display_name:<20} | CALL     | ROLE: PLAYER"
            f"{Colors.RESET}"
        )
        print(line)

    @classmethod
    def log_callback_response(cls, callback_name: str) -> None:
        """Log callback response (ORANGE)."""
        display_name = CALLBACK_DISPLAY_NAMES.get(callback_name, callback_name)
        time_str = cls._format_time(with_ms=True)
        line = (
            f"{Colors.ORANGE}"
            f"{time_str} | CALLBACK: {display_name:<20} | RESPONSE | ROLE: PLAYER"
            f"{Colors.RESET}"
        )
        print(line)


# Convenience functions
def log_received(msg_type: str, sender_email: str, game_id: str = None, deadline: str = None) -> None:
    ProtocolLogger.log_received(msg_type, sender_email, game_id, deadline)


def log_sent(msg_type: str, recipient_email: str, game_id: str = None, deadline: str = None) -> None:
    ProtocolLogger.log_sent(msg_type, recipient_email, game_id, deadline)


def log_rejected(msg_type: str, sender_email: str, reason: str = "") -> None:
    ProtocolLogger.log_rejected(msg_type, sender_email, reason)


def log_error(message: str) -> None:
    ProtocolLogger.log_error(message)


def log_callback_call(callback_name: str) -> None:
    ProtocolLogger.log_callback_call(callback_name)


def log_callback_response(callback_name: str) -> None:
    ProtocolLogger.log_callback_response(callback_name)


def set_game_context(game_id: str, player_active: bool = True) -> None:
    ProtocolLogger.set_game_context(game_id, player_active)
