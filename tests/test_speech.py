from pathlib import Path
from types import SimpleNamespace
import tempfile
import json
import unittest
from unittest.mock import Mock, patch

from speech.conversation import VoiceConversation
from speech.recorder import MicrophoneRecorder
from speech.whisper import TranscriptionError, WhisperTranscriber


class SpeechTests(unittest.TestCase):
    def test_recorder_rejects_invalid_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                MicrophoneRecorder().record_for(Path(directory) / "audio.wav", 0)

    def test_whisper_reads_generated_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "whisper.cpp" / "Release"
            runtime.mkdir(parents=True)
            (runtime / "whisper-cli.exe").touch()
            models = root / "models"
            models.mkdir()
            (models / "ggml-base.bin").touch()
            audio = root / "command.wav"
            audio.touch()

            def fake_run(command, **kwargs):
                Path(command[command.index("-of") + 1] + ".txt").write_text(
                    "Hola ODIN", encoding="utf-8"
                )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("speech.whisper.subprocess.run", side_effect=fake_run):
                self.assertEqual(WhisperTranscriber(root).transcribe(audio), "Hola ODIN")
                self.assertEqual(list(root.glob("command-*.txt")), [])

    def test_whisper_can_use_lightweight_base_model_and_two_threads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "whisper.cpp" / "Release"
            runtime.mkdir(parents=True)
            (runtime / "whisper-cli.exe").touch()
            models = root / "models"
            models.mkdir()
            base = models / "ggml-base.bin"
            base.touch()
            audio = root / "wake.wav"
            audio.touch()

            def fake_run(command, **kwargs):
                Path(command[command.index("-of") + 1] + ".txt").write_text(
                    "Olín, estado", encoding="utf-8"
                )
                self.assertEqual(command[command.index("-t") + 1], "2")
                self.assertIn(str(base), command)
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("speech.whisper.subprocess.run", side_effect=fake_run):
                transcriber = WhisperTranscriber(
                    root, model_preference="base", threads=2
                )
                self.assertEqual(transcriber.transcribe(audio), "Olín, estado")

    def test_whisper_reports_missing_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(TranscriptionError):
                WhisperTranscriber(root).transcribe(root / "audio.wav")

    def test_whisper_exposes_average_word_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "whisper.cpp" / "Release"
            runtime.mkdir(parents=True)
            (runtime / "whisper-cli.exe").touch()
            models = root / "models"
            models.mkdir()
            (models / "ggml-base.bin").touch()
            audio = root / "command.wav"
            audio.touch()

            def fake_run(command, **kwargs):
                payload = {
                    "transcription": [{
                        "text": " combustible",
                        "tokens": [
                            {"text": " combustible", "p": 0.8},
                            {"text": "[_EOT_]", "p": 0.99},
                        ],
                    }]
                }
                Path(command[command.index("-of") + 1] + ".json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("speech.whisper.subprocess.run", side_effect=fake_run):
                text, confidence = WhisperTranscriber(root).transcribe_with_confidence(audio)

            self.assertEqual(text, "combustible")
            self.assertEqual(confidence, 0.8)

    def test_conversation_connects_recording_ai_and_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = SimpleNamespace(data_root=root)
            recorder = Mock()
            transcriber = Mock()
            transcriber.transcribe.return_value = "Estado de la nave"
            assistant = Mock()
            assistant.ask.return_value = SimpleNamespace(text="Todo operativo, comandante.")
            voice = Mock()

            conversation = VoiceConversation(config, recorder, transcriber, assistant, voice)
            question, answer = conversation.listen_once(3)

            recorder.record_for.assert_called_once_with(
                root / "speech" / "last_command.wav", 3
            )
            assistant.ask.assert_called_once_with("Estado de la nave", context="")
            voice.speak.assert_called_once_with("ODIN", "Todo operativo, comandante.")
            self.assertEqual(
                (question, answer), ("Estado de la nave", "Todo operativo, comandante.")
            )


if __name__ == "__main__":
    unittest.main()
