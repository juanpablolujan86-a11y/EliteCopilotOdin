import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voice.elevenlabs import ElevenLabsClient, ElevenLabsError
from voice.settings import VoiceSettingsRepository


class VoiceSettingsTests(unittest.TestCase):
    def test_assignments_are_independent_and_contain_no_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = VoiceSettingsRepository(Path(directory))
            settings = repository.load()
            settings.officers["ODIN"].voice = "Microsoft Raul - Spanish (Mexico)"
            settings.officers["MÍMIR"].voice = "voice_id_mimir"
            settings.officers["MÍMIR"].provider = "elevenlabs"
            repository.save(settings)

            loaded = repository.load()
            self.assertEqual(
                loaded.officers["ODIN"].voice,
                "Microsoft Raul - Spanish (Mexico)",
            )
            self.assertEqual(loaded.officers["MÍMIR"].voice, "voice_id_mimir")
            self.assertEqual(loaded.officers["MÍMIR"].provider, "elevenlabs")
            payload = json.loads(repository.path.read_text(encoding="utf-8"))
            self.assertNotIn("api_key", json.dumps(payload).lower())


class ElevenLabsClientTests(unittest.TestCase):
    @patch("voice.elevenlabs.requests.get")
    def test_validates_subscription_without_persisting_key(self, get: Mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "tier": "free",
            "status": "active",
            "character_count": 20,
            "character_limit": 10000,
        }
        get.return_value = response

        result = ElevenLabsClient().validate("temporary-secret")

        self.assertEqual(result.tier, "free")
        self.assertEqual(result.used, 20)
        self.assertEqual(
            get.call_args.kwargs["headers"]["xi-api-key"], "temporary-secret"
        )

    @patch("voice.elevenlabs.requests.get")
    def test_rejected_key_returns_safe_error(self, get: Mock):
        get.return_value = Mock(status_code=401)
        with self.assertRaisesRegex(ElevenLabsError, "rechazó"):
            ElevenLabsClient().validate("invalid-secret")

    def test_empty_key_is_rejected_before_network_call(self):
        with self.assertRaisesRegex(ElevenLabsError, "vacía"):
            ElevenLabsClient().validate("  ")


if __name__ == "__main__":
    unittest.main()
