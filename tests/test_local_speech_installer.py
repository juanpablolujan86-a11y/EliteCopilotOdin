import unittest

from installer.local_speech_gui import PACKAGES, _human_bytes


class LocalSpeechInstallerTests(unittest.TestCase):
    def test_uses_official_model_packages(self):
        self.assertEqual(len(PACKAGES), 2)
        self.assertTrue(all("k2-fsa/sherpa-onnx/releases" in item.url for item in PACKAGES))
        self.assertTrue(PACKAGES[0].directory.endswith("v3-int8"))
        self.assertEqual(PACKAGES[1].directory, "kokoro-int8-multi-lang-v1_0")

    def test_formats_download_size(self):
        self.assertEqual(_human_bytes(1024 * 1024), "1.0 MB")


if __name__ == "__main__":
    unittest.main()
