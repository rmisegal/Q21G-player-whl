"""
My Q21 Player Implementation.

Implement the four required methods to play the 21-Questions game.
"""

from q21_player import PlayerAI


class MyPlayerAI(PlayerAI):
    """
    Your custom player AI.

    Implement all four methods below to create your game-playing strategy.
    """

    def get_warmup_answer(self, ctx: dict) -> dict:
        """
        Answer the warmup math question.

        Args:
            ctx: Context with ctx["dynamic"]["warmup_question"] containing
                 a simple math question like "What is 2 + 2?"

        Returns:
            {"answer": "4"}  # Your numeric answer as a string
        """
        question = ctx["dynamic"]["warmup_question"]
        # TODO: Parse and solve the math question
        return {"answer": "0"}

    def get_questions(self, ctx: dict) -> dict:
        """
        Generate 20 yes/no questions to identify the book's opening sentence.

        Args:
            ctx: Context with:
                - ctx["dynamic"]["book_name"]: Name of the book
                - ctx["dynamic"]["book_hint"]: Hint about the book
                - ctx["dynamic"]["association_word"]: Thematic word

        Returns:
            {"questions": [
                {
                    "question_number": 1,
                    "question_text": "Does the opening mention a character?",
                    "options": {"A": "Yes", "B": "No", "C": "Partially", "D": "Unknown"}
                },
                ... # 20 questions total
            ]}
        """
        book_name = ctx["dynamic"]["book_name"]
        book_hint = ctx["dynamic"].get("book_hint", "")

        # TODO: Generate strategic questions to narrow down the opening sentence
        questions = []
        for i in range(1, 21):
            questions.append({
                "question_number": i,
                "question_text": f"Question {i} about {book_name}?",
                "options": {"A": "Yes", "B": "No", "C": "Partially", "D": "Unknown"}
            })
        return {"questions": questions}

    def get_guess(self, ctx: dict) -> dict:
        """
        Guess the book's opening sentence based on the answers received.

        Args:
            ctx: Context with:
                - ctx["dynamic"]["answers"]: List of 20 answers (A/B/C/D)
                - ctx["dynamic"]["book_name"]: Name of the book
                - ctx["dynamic"]["book_hint"]: Hint about the book
                - ctx["dynamic"]["association_word"]: Thematic word

        Returns:
            {
                "opening_sentence": "It was a dark and stormy night.",
                "sentence_justification": "Based on answers... (35+ words)",
                "associative_word": "mystery",
                "word_justification": "This word relates to... (35+ words)",
                "confidence": 0.7  # 0.0 to 1.0
            }
        """
        answers = ctx["dynamic"]["answers"]
        book_name = ctx["dynamic"].get("book_name", "Unknown")

        # TODO: Analyze answers to deduce the opening sentence
        return {
            "opening_sentence": "The story begins with an unknown opening.",
            "sentence_justification": (
                "Based on the pattern of answers received to the twenty questions, "
                "I analyzed the responses to determine the most likely opening. "
                "The combination of affirmative and negative answers suggests "
                "a particular narrative style and tone for this book."
            ),
            "associative_word": "beginning",
            "word_justification": (
                "The word 'beginning' was selected because it represents the "
                "fundamental concept of story openings and narrative structure. "
                "This thematic connection aligns with the patterns observed "
                "in the answer responses throughout the questioning phase."
            ),
            "confidence": 0.5
        }

    def on_score_received(self, ctx: dict) -> None:
        """
        Called when you receive your score for a completed game.

        Args:
            ctx: Context with:
                - ctx["dynamic"]["league_points"]: Points earned (0-100)
                - ctx["dynamic"]["match_id"]: The match identifier
        """
        points = ctx["dynamic"].get("league_points", 0)
        match_id = ctx["dynamic"].get("match_id", "unknown")
        print(f"Game {match_id} complete! Scored {points} points.")
