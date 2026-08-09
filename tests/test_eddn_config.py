import json
import tempfile
import threading
import unittest
from pathlib import Path

from core.config import Config


class EDDNConfigTests(unittest.TestCase):
    @staticmethod
    def config(data):
        config=Config.__new__(Config)
        config.data=data
        return config

    def test_all_network_features_are_safe_by_default(self):
        config=self.config({})
        self.assertFalse(config.eddn_capture_enabled)
        self.assertFalse(config.eddn_upload_enabled)
        self.assertTrue(config.eddn_test_mode)

    def test_live_mode_requires_explicit_false_value(self):
        self.assertFalse(self.config({"eddn_test_mode":False}).eddn_test_mode)
        self.assertFalse(self.config({"eddn_test_mode":"false"}).eddn_test_mode)
        self.assertTrue(self.config({"eddn_test_mode":"true"}).eddn_test_mode)

    def test_both_voice_activation_modes_are_enabled_by_default(self):
        config = self.config({})
        self.assertTrue(config.push_to_talk_enabled)
        self.assertTrue(config.wake_word_enabled)

    def test_desktop_geometry_accepts_secondary_monitor_coordinates(self):
        self.assertEqual(
            self.config({"desktop_geometry": "1180x720-1920+120"}).desktop_geometry,
            "1180x720-1920+120",
        )
        self.assertEqual(self.config({"desktop_geometry": "invalid"}).desktop_geometry, "")

    def test_network_preferences_are_persisted_outside_project_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.config({})
            config.data_root = Path(directory)
            config.preferences_file = config.data_root / "preferences.json"
            config._preferences_lock = threading.Lock()

            config.update_preferences(
                eddn_capture_enabled=True,
                eddn_upload_enabled=True,
                ignored_secret="never-written",
            )

            payload = json.loads(config.preferences_file.read_text(encoding="utf-8"))
            self.assertTrue(payload["eddn_capture_enabled"])
            self.assertTrue(payload["eddn_upload_enabled"])
            self.assertNotIn("ignored_secret", payload)
            self.assertTrue(config.eddn_upload_enabled)


if __name__=="__main__": unittest.main()
