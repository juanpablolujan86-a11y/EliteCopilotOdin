import unittest
from pathlib import Path
from unittest.mock import patch

from platform_adapters.audio import (
    AudioAdapterUnavailable,
    create_audio_player,
    create_speech_player,
)
from voice.playback import WindowsMp3Player, WindowsSpeechPlayer


class AudioAdapterTests(unittest.TestCase):
    @patch("platform_adapters.audio.platform.system", return_value="Windows")
    def test_windows_selects_native_players(self, _system):
        audio = create_audio_player(Path("cache"))
        speech = create_speech_player()
        self.assertIsInstance(audio, WindowsMp3Player)
        self.assertIsInstance(speech, WindowsSpeechPlayer)

    @patch("platform_adapters.audio.platform.system", return_value="Linux")
    def test_unsupported_platform_fails_explicitly(self, _system):
        with self.assertRaises(AudioAdapterUnavailable):
            create_audio_player()
        with self.assertRaises(AudioAdapterUnavailable):
            create_speech_player()


if __name__ == "__main__":
    unittest.main()
