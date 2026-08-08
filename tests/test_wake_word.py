import unittest

from speech.wake_word import interpret_wake_phrase


class WakeWordTests(unittest.TestCase):
    def test_ignores_conversation_without_wake_word(self) -> None:
        self.assertEqual(interpret_wake_phrase("qué buen planeta"), (None, False))

    def test_accepts_wake_word_and_question_in_one_phrase(self) -> None:
        self.assertEqual(
            interpret_wake_phrase("ODIN, cuántos créditos tengo"),
            ("cuántos créditos tengo", False),
        )

    def test_wake_word_alone_arms_next_phrase(self) -> None:
        self.assertEqual(interpret_wake_phrase("Odín"), (None, True))
        self.assertEqual(
            interpret_wake_phrase("datos de mi nave", waiting_for_question=True),
            ("datos de mi nave", False),
        )

    def test_f8_accepts_phrase_without_wake_word(self) -> None:
        self.assertEqual(
            interpret_wake_phrase("estado general", forced=True),
            ("estado general", False),
        )


if __name__ == "__main__":
    unittest.main()
