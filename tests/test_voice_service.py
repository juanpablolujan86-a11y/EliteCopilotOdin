import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from voice.service import OfficerVoiceService, VoiceServiceError
from voice.settings import VoiceSettingsRepository


class OfficerVoiceServiceTests(unittest.TestCase):
    def test_uses_officer_voice_and_protected_key(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SimpleNamespace(data_root=Path(directory))
            repository = VoiceSettingsRepository(config.data_root)
            settings = repository.load()
            settings.officers["ODIN"].provider = "elevenlabs"
            settings.officers["ODIN"].voice = "voice-brian"
            repository.save(settings)
            credentials = Mock()
            credentials.get.return_value = "protected-secret"
            client = Mock()
            client.synthesize.return_value = b"mp3-data"
            player = Mock()

            service = OfficerVoiceService(config, credentials, client, player, Mock())
            service.speak("ODIN", "Prueba")

            client.synthesize.assert_called_once_with(
                "protected-secret", "voice-brian", "Prueba"
            )
            player.play.assert_called_once_with(b"mp3-data")

    def test_windows_provider_uses_free_local_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SimpleNamespace(data_root=Path(directory))
            repository = VoiceSettingsRepository(config.data_root)
            settings = repository.load()
            settings.officers["ODIN"].provider = "windows"
            settings.officers["ODIN"].voice = "Microsoft Raul - Spanish (Mexico)"
            repository.save(settings)
            windows_player = Mock()
            service = OfficerVoiceService(config, Mock(), Mock(), Mock(), windows_player)
            service.speak("ODIN", "Prueba")
            windows_player.speak.assert_called_once_with(
                "Prueba", "Microsoft Raul - Spanish (Mexico)", 0, 100
            )

    def test_edge_provider_generates_and_plays_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SimpleNamespace(data_root=Path(directory))
            player = Mock()
            edge_client = Mock()
            edge_client.synthesize.return_value = b"edge-mp3"
            service = OfficerVoiceService(
                config, Mock(), Mock(), player, Mock(), edge_client
            )

            service.speak("ODIN", "Prueba")

            edge_client.synthesize.assert_called_once_with(
                "Prueba", "es-AR-TomasNeural", rate=0, volume=100
            )
            player.play.assert_called_once_with(b"edge-mp3")

    def test_elevenlabs_failure_falls_back_to_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SimpleNamespace(data_root=Path(directory))
            repository = VoiceSettingsRepository(config.data_root)
            settings = repository.load()
            settings.officers["ODIN"].provider = "elevenlabs"
            settings.officers["ODIN"].voice = "voice-brian"
            repository.save(settings)
            credentials = Mock()
            credentials.get.return_value = "protected-secret"
            client = Mock()
            from voice.elevenlabs import ElevenLabsError
            client.synthesize.side_effect = ElevenLabsError("sin cuota")
            windows_player = Mock()

            service = OfficerVoiceService(config, credentials, client, Mock(), windows_player)
            service.speak("ODIN", "Prueba")

            windows_player.speak.assert_called_once_with(
                "Prueba", "Microsoft Raul - Spanish (Mexico)", 0, 100
            )


if __name__ == "__main__":
    unittest.main()
