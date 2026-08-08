import unittest
from pathlib import Path
from unittest.mock import Mock

from speech.wake_word import WakeWordListener, interpret_wake_phrase


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

    def test_accepts_real_whisper_olin_confusion(self) -> None:
        self.assertEqual(
            interpret_wake_phrase("Olín, vamos a casa"),
            ("vamos a casa", False),
        )

    def test_f8_accepts_phrase_without_wake_word(self) -> None:
        self.assertEqual(
            interpret_wake_phrase("estado general", forced=True),
            ("estado general", False),
        )

    def test_forced_retry_keeps_full_command_silence(self) -> None:
        recorder = Mock()
        listener = WakeWordListener(
            Path("."), Mock(), recorder=recorder, transcriber=Mock()
        )
        recorder.record_utterance.side_effect = lambda *args, **kwargs: (
            listener.stop() or None
        )
        listener.arm()

        listener.run()

        self.assertEqual(
            recorder.record_utterance.call_args.kwargs["silence_seconds"], 1.0
        )

    def test_low_confidence_command_requests_retry_instead_of_answering(self) -> None:
        recorder = Mock()
        recorder.record_utterance.return_value = Path("unclear.wav")
        transcriber = Mock()
        transcriber.transcribe_with_confidence.return_value = ("Kans Simer", 0.42)
        unclear = Mock()
        listener = WakeWordListener(
            Path("."), Mock(), on_unclear=unclear,
            recorder=recorder, transcriber=transcriber,
        )

        def stop_after_unclear() -> None:
            unclear()
            listener.stop()

        listener.on_unclear = stop_after_unclear
        listener.arm()
        listener.run()

        unclear.assert_called_once_with()
        self.assertTrue(listener.paused.is_set())

    def test_wake_word_alone_announces_activation_before_next_phrase(self) -> None:
        recorder = Mock()
        recorder.record_utterance.return_value = Path("wake.wav")
        transcriber = Mock()
        transcriber.transcribe_with_confidence.return_value = ("ODIN", 1.0)
        activated = Mock()
        listener = WakeWordListener(
            Path("."), Mock(), activated, recorder=recorder, transcriber=transcriber
        )

        def stop_after_activation() -> None:
            activated()
            listener.stop()

        listener.on_activation = stop_after_activation
        listener.run()

        activated.assert_called_once_with()
        self.assertTrue(listener.paused.is_set())
        self.assertEqual(
            recorder.record_utterance.call_args.kwargs["silence_seconds"], 0.25
        )


if __name__ == "__main__":
    unittest.main()
