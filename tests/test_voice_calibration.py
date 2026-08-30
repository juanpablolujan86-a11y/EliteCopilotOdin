import tempfile
import unittest
from pathlib import Path

from core.database import DatabaseManager
from intelligence.command_memory import VoiceCommandMemory
from intelligence.voice_calibration import VoiceCalibrationManager


class VoiceCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(Path(self.temporary.name))
        self.database.connect()
        self.database.create_tables()
        self.memory = VoiceCommandMemory(self.database)
        self.calibration = VoiceCalibrationManager(self.memory)

    def tearDown(self) -> None:
        self.database.disconnect()
        self.temporary.cleanup()

    def test_requires_explicit_consent_before_enrolling(self) -> None:
        with self.assertRaisesRegex(ValueError, "consentimiento"):
            self.calibration.enroll("cmdr-a", "y gaseer comercio", "trade")

    def test_transcript_resolves_to_safe_calibrated_command(self) -> None:
        self.calibration.begin("cmdr-a")
        self.calibration.enroll("cmdr-a", "y gaseer comercio", "trade")

        learned = self.memory.resolve("cmdr-a", "y gaseer comercio")

        self.assertIsNotNone(learned)
        self.assertEqual(learned.intent, "freyja_trade_menu")
        self.assertEqual(self.calibration.status("cmdr-a")["sample_count"], 1)
        self.assertIsNone(self.memory.resolve("cmdr-b", "y gaseer comercio"))

    def test_rejects_unapproved_intent_key(self) -> None:
        self.calibration.begin("cmdr-a")
        with self.assertRaisesRegex(ValueError, "no está permitida"):
            self.calibration.enroll("cmdr-a", "borra todo", "arbitrary_action")

    def test_delete_removes_profile_and_all_learned_phrases(self) -> None:
        self.memory.remember("cmdr-a", "llévame al rancho", "home_route", {})
        self.calibration.begin("cmdr-a")
        self.calibration.enroll("cmdr-a", "je vame a casa", "home")

        removed = self.calibration.delete("cmdr-a")

        self.assertEqual(removed, 2)
        self.assertFalse(self.calibration.status("cmdr-a")["consented"])
        self.assertEqual(self.memory.count("cmdr-a"), 0)

    def test_confirmed_acoustic_samples_produce_bounded_private_profile(self) -> None:
        self.calibration.begin("cmdr-a")
        self.calibration.enroll(
            "cmdr-a", "y gaseer comercio", "trade", duration=2.4, rms=1800,
        )

        status = self.calibration.status("cmdr-a")

        self.assertEqual(status["acoustic_samples"], 1)
        self.assertAlmostEqual(status["average_duration"], 2.4)
        self.assertGreaterEqual(status["silence_seconds"], 0.8)
        self.assertLessEqual(status["silence_seconds"], 1.25)
        self.assertGreaterEqual(status["threshold_multiplier"], 2.7)
        self.assertLessEqual(status["threshold_multiplier"], 3.8)


if __name__ == "__main__":
    unittest.main()
