import unittest
from unittest.mock import Mock, patch

from voice.edge import EDGE_LATIN_VOICES, EdgeTtsClient, EdgeTtsError


class EdgeTtsClientTests(unittest.TestCase):
    @patch("voice.edge.edge_tts.Communicate")
    def test_collects_audio_chunks_with_latin_voice(self, communicate: Mock):
        communication = Mock()
        communication.stream_sync.return_value = iter([
            {"type": "audio", "data": b"first"},
            {"type": "WordBoundary", "offset": 1},
            {"type": "audio", "data": b"second"},
        ])
        communicate.return_value = communication
        audio = EdgeTtsClient().synthesize("Prueba", EDGE_LATIN_VOICES["ODIN"], rate=1)
        self.assertEqual(audio, b"firstsecond")
        self.assertEqual(communicate.call_args.kwargs["voice"], "es-AR-TomasNeural")
        self.assertEqual(communicate.call_args.kwargs["rate"], "+10%")

    @patch("voice.edge.edge_tts.Communicate")
    def test_empty_audio_fails_safely(self, communicate: Mock):
        communication = Mock()
        communication.stream_sync.return_value = iter([])
        communicate.return_value = communication
        with self.assertRaisesRegex(EdgeTtsError, "vacío"):
            EdgeTtsClient().synthesize("Prueba", EDGE_LATIN_VOICES["MÍMIR"])

    def test_presets_exclude_spain(self):
        self.assertTrue(all(not voice.startswith("es-ES") for voice in EDGE_LATIN_VOICES.values()))

    def test_heimdall_uses_masculine_mexican_voice(self):
        self.assertEqual(EDGE_LATIN_VOICES["HEIMDALL"], "es-MX-JorgeNeural")


if __name__ == "__main__":
    unittest.main()
