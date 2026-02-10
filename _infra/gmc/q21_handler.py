"""Q21 Handler - routes Q21 messages to appropriate phase handlers.

This module handles all Q21G protocol messages from the referee
and routes them to the appropriate game phase handlers.
"""
from typing import Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class Q21Response:
    """Response data from handling a Q21 message."""
    message_type: str
    payload: dict
    recipient: str
    correlation_id: Optional[str] = None


class Q21Handler:
    """Routes Q21 messages to appropriate game phase handlers.

    Handles the following message types:
    - Q21_WARMUP_CALL -> execute warmup phase
    - Q21_ROUND_START -> initialize round and trigger questions
    - Q21_QUESTIONS_CALL -> generate questions
    - Q21_ANSWERS_BATCH -> receive answers and submit guess
    - Q21_SCORE_FEEDBACK -> handle score notification
    """

    # Message type constants
    WARMUP_CALL = "Q21_WARMUP_CALL"
    ROUND_START = "Q21_ROUND_START"
    QUESTIONS_CALL = "Q21_QUESTIONS_CALL"
    ANSWERS_BATCH = "Q21_ANSWERS_BATCH"
    SCORE_FEEDBACK = "Q21_SCORE_FEEDBACK"

    def __init__(self) -> None:
        """Initialize the Q21Handler with message routing table."""
        self._handlers: dict[str, Callable[..., Optional[Q21Response]]] = {
            self.WARMUP_CALL: self._handle_warmup,
            self.ROUND_START: self._handle_round_start,
            self.QUESTIONS_CALL: self._handle_questions,
            self.ANSWERS_BATCH: self._handle_answers,
            self.SCORE_FEEDBACK: self._handle_score,
        }

    def dispatch(
        self,
        msg_type: str,
        payload: dict[str, Any],
        sender: str,
        player_email: str,
        request_id: Optional[str] = None
    ) -> Optional[Q21Response]:
        """Dispatch Q21 message to appropriate handler.

        Args:
            msg_type: The Q21 message type (e.g., Q21_WARMUP_CALL).
            payload: Message payload containing game data.
            sender: Sender email (referee).
            player_email: Player's email address.
            request_id: Optional correlation/request ID.

        Returns:
            Q21Response with response data, or None if no response needed.

        Raises:
            ValueError: If message type is unknown.
        """
        handler = self._handlers.get(msg_type)
        if handler is None:
            raise ValueError(f"Unknown Q21 message type: {msg_type}")

        return handler(payload, sender, player_email, request_id)

    def _handle_warmup(
        self,
        payload: dict[str, Any],
        sender: str,
        player_email: str,
        request_id: Optional[str]
    ) -> Q21Response:
        """Handle Q21_WARMUP_CALL - solve warmup question."""
        raise NotImplementedError("Q21Handler._handle_warmup() - Part 4")

    def _handle_round_start(
        self,
        payload: dict[str, Any],
        sender: str,
        player_email: str,
        request_id: Optional[str]
    ) -> Q21Response:
        """Handle Q21_ROUND_START - store book info and trigger questions."""
        raise NotImplementedError("Q21Handler._handle_round_start() - Part 5")

    def _handle_questions(
        self,
        payload: dict[str, Any],
        sender: str,
        player_email: str,
        request_id: Optional[str]
    ) -> Q21Response:
        """Handle Q21_QUESTIONS_CALL - generate 20 questions."""
        raise NotImplementedError("Q21Handler._handle_questions() - Part 5")

    def _handle_answers(
        self,
        payload: dict[str, Any],
        sender: str,
        player_email: str,
        request_id: Optional[str]
    ) -> Q21Response:
        """Handle Q21_ANSWERS_BATCH - receive answers and submit guess."""
        raise NotImplementedError("Q21Handler._handle_answers() - Part 6")

    def _handle_score(
        self,
        payload: dict[str, Any],
        sender: str,
        player_email: str,
        request_id: Optional[str]
    ) -> Optional[Q21Response]:
        """Handle Q21_SCORE_FEEDBACK - process game score.

        Returns None as score feedback doesn't require a response.
        """
        raise NotImplementedError("Q21Handler._handle_score() - Part 7")
