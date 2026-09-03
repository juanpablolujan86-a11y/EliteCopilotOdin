import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import Config


class SpeechProviderConfigTests(unittest.TestCase):
    def test_provider_defaults_to_auto_and_persists(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            "os.environ", {"LOCALAPPDATA": folder}
        ):
            config = Config()
            self.assertEqual(config.speech_recognition_provider, "auto")
            config.update_preferences(speech_recognition_provider="parakeet")
            self.assertEqual(Config().speech_recognition_provider, "parakeet")
            payload = json.loads((Path(folder) / "ODIN" / "preferences.json").read_text())
            self.assertEqual(payload["speech_recognition_provider"], "parakeet")

    def test_unknown_provider_recovers_to_auto(self):
        config = object.__new__(Config)
        config.data = {"speech_recognition_provider": "unknown"}
        self.assertEqual(config.speech_recognition_provider, "auto")


if __name__ == "__main__":
    unittest.main()
