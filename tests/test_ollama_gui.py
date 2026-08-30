import unittest

from installer.ollama_gui import _human_bytes, _parse_size


class OllamaInstallerDisplayTests(unittest.TestCase):
    def test_parses_ollama_transfer_units(self):
        self.assertEqual(_parse_size("500 MB"), 500 * 1024**2)
        self.assertEqual(_parse_size("2.5 GB"), 2.5 * 1024**3)

    def test_formats_remaining_download(self):
        remaining = _parse_size("4 GB") - _parse_size("1.5 GB")
        self.assertEqual(_human_bytes(remaining), "2.5 GB")


if __name__ == "__main__":
    unittest.main()
