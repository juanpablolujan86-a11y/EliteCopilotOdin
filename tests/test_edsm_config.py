import unittest

from core.config import Config


class EDSMConfigTests(unittest.TestCase):
    def _config(self, values=None):
        config = Config.__new__(Config)
        config.data = values or {}
        return config

    def test_private_capture_and_upload_are_disabled_by_default(self):
        config = self._config()
        self.assertFalse(config.edsm_capture_enabled)
        self.assertFalse(config.edsm_upload_enabled)

    def test_private_capture_and_upload_are_independent(self):
        config = self._config({
            "edsm_capture_enabled": False,
            "edsm_upload_enabled": True,
        })
        self.assertFalse(config.edsm_capture_enabled)
        self.assertTrue(config.edsm_upload_enabled)

    def test_spanish_affirmative_value_is_supported(self):
        config = self._config({"edsm_capture_enabled": "sí"})
        self.assertTrue(config.edsm_capture_enabled)


if __name__ == "__main__":
    unittest.main()
