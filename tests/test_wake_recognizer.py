import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from speech.wake_recognizer import VoskWakeRecognizer


class WakeRecognizerTests(unittest.TestCase):
    def test_uses_closed_spanish_vocabulary_for_fast_wake_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "wake.wav"
            with wave.open(str(audio), "wb") as recording:
                recording.setnchannels(1)
                recording.setsampwidth(2)
                recording.setframerate(16_000)
                recording.writeframes(b"\0\0" * 160)

            recognizer = Mock()
            recognizer.FinalResult.return_value = '{"text": "odin"}'
            vosk = SimpleNamespace(
                Model=Mock(return_value=Mock()),
                SetLogLevel=Mock(),
                KaldiRecognizer=Mock(return_value=recognizer),
            )
            with patch.dict(sys.modules, {"vosk": vosk}):
                wake = VoskWakeRecognizer(root / "model")
                self.assertEqual(wake.transcribe(audio), "odin")

            grammar = vosk.KaldiRecognizer.call_args.args[2]
            self.assertIn("odin", grammar)
            recognizer.AcceptWaveform.assert_called_once()


if __name__ == "__main__":
    unittest.main()
