import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voice.elevenlabs import ElevenLabsClient, ElevenLabsError
from voice.key_file import PLACEHOLDER, import_key_file
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

    @patch("voice.elevenlabs.requests.get")
    def test_lists_voices_owned_by_current_account(self, get: Mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "voices": [
                {
                    "voice_id": "voice-b",
                    "name": "Beta",
                    "category": "premade",
                    "verified_languages": [{"language": "en", "accent": "american"}],
                },
                {
                    "voice_id": "voice-a",
                    "name": "Alfa",
                    "category": "cloned",
                    "verified_languages": [{"language": "es", "accent": "latin american"}],
                },
            ]
        }
        get.return_value = response

        voices = ElevenLabsClient().list_voices("personal-key")

        self.assertEqual([voice.name for voice in voices], ["Alfa", "Beta"])
        self.assertEqual(voices[0].voice_id, "voice-a")
        self.assertTrue(voices[0].is_latin_spanish)
        self.assertFalse(voices[1].is_latin_spanish)


class KeyFileImportTests(unittest.TestCase):
    def test_key_is_migrated_and_removed_from_text_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ELEVENLABS_API_KEY.txt"
            path.write_text("personal-secret\n", encoding="utf-8")
            credentials = Mock()
            client = Mock()

            result = import_key_file(root, credentials, client)

            self.assertTrue(result.imported)
            client.list_voices.assert_called_once_with("personal-secret")
            credentials.set.assert_called_once_with("personal-secret")
            cleaned = path.read_text(encoding="utf-8")
            self.assertIn(PLACEHOLDER, cleaned)
            self.assertNotIn("personal-secret", cleaned)

    def test_invalid_key_is_not_stored_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ELEVENLABS_API_KEY.txt"
            path.write_text("invalid-secret\n", encoding="utf-8")
            credentials = Mock()
            client = Mock()
            client.list_voices.side_effect = ElevenLabsError("rechazada")

            result = import_key_file(root, credentials, client)

            self.assertFalse(result.imported)
            credentials.set.assert_not_called()
            self.assertEqual(path.read_text(encoding="utf-8"), "invalid-secret\n")


if __name__ == "__main__":
    unittest.main()
