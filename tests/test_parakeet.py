import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

from speech.parakeet import ParakeetTranscriber
from speech.transcriber import FallbackTranscriber
from speech.whisper import TranscriptionError


class ParakeetTranscriberTests(unittest.TestCase):
    def test_availability_requires_complete_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            transcriber = ParakeetTranscriber(root)
            self.assertFalse(transcriber.available)
            for name in transcriber.REQUIRED_FILES:
                (root / name).touch()
            self.assertTrue(transcriber.available)

    def test_transcribes_pcm_wav_with_cached_recognizer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ParakeetTranscriber.REQUIRED_FILES:
                (root / name).touch()
            audio = root / "command.wav"
            with wave.open(str(audio), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(16000)
                target.writeframes(b"\x00\x00" * 160)
            stream = Mock()
            stream.result.text = "ODIN solicita atraque"
            recognizer = Mock()
            recognizer.create_stream.return_value = stream
            module = Mock()
            module.OfflineRecognizer.from_transducer.return_value = recognizer
            with patch.dict("sys.modules", {"sherpa_onnx": module}):
                transcriber = ParakeetTranscriber(root)
                self.assertEqual(transcriber.transcribe(audio), "ODIN solicita atraque")
                self.assertEqual(transcriber.transcribe(audio), "ODIN solicita atraque")
            module.OfflineRecognizer.from_transducer.assert_called_once()

    def test_fallback_is_used_when_primary_fails(self):
        primary = Mock()
        primary.transcribe.side_effect = TranscriptionError("sin modelo")
        fallback = Mock()
        fallback.transcribe.return_value = "orden reconocida"
        self.assertEqual(
            FallbackTranscriber(primary, fallback).transcribe(Path("audio.wav")),
            "orden reconocida",
        )


if __name__ == "__main__":
    unittest.main()
