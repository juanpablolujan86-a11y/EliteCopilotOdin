import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from installer.local_speech_gui import PACKAGES, package_complete, validate_recognition
from installer.speech_readiness import has_recognition_models


class SpeechRepairTests(unittest.TestCase):
    def test_clean_profile_has_no_recognition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = SimpleNamespace(data_root=root, speech_recognition_provider="auto",
                parakeet_model_root=root / "parakeet", faster_whisper_model_root=root / "models")
            self.assertFalse(has_recognition_models(config))
            config.parakeet_model_root.mkdir()
            for name in PACKAGES[0].required:
                (config.parakeet_model_root / name).write_bytes(b"test")
            self.assertTrue(has_recognition_models(config))
            (config.parakeet_model_root / "tokens.txt").write_bytes(b"")
            self.assertFalse(has_recognition_models(config))

    def test_partial_package_not_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertFalse(package_complete(root, PACKAGES[0]))
            for name in PACKAGES[0].required:
                (root / name).write_bytes(b"")
            self.assertFalse(package_complete(root, PACKAGES[0]))

    def test_runtime_load_failure_is_not_success(self):
        with patch("speech.parakeet.ParakeetTranscriber") as engine:
            engine.return_value.warm_up.return_value = False
            with self.assertRaises(RuntimeError):
                validate_recognition(Path("unused"))
            engine.return_value.warm_up.return_value = True
            validate_recognition(Path("unused"))
