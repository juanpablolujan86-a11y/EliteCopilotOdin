import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voice.kokoro import KokoroTtsClient


class KokoroTtsClientTests(unittest.TestCase):
    def test_creates_wav_and_reuses_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in KokoroTtsClient.REQUIRED_FILES:
                (root / name).touch()
            audio = Mock(samples=[0.0, 0.25, -0.25], sample_rate=24000)
            engine = Mock()
            engine.generate.return_value = audio
            config = Mock()
            config.validate.return_value = True
            module = Mock()
            module.OfflineTtsConfig.return_value = config
            module.OfflineTts.return_value = engine
            with patch.dict("sys.modules", {"sherpa_onnx": module}):
                client = KokoroTtsClient(root)
                first = client.synthesize("Sí, comandante", "2")
                second = client.synthesize("Adelante", "2")
            self.assertEqual(first[:4], b"RIFF")
            self.assertEqual(second[8:12], b"WAVE")
            module.OfflineTts.assert_called_once_with(config)
            engine.generate.assert_called_with("Adelante", sid=2, speed=1.0)


if __name__ == "__main__":
    unittest.main()
