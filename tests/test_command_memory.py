from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager
from intelligence.command_memory import VoiceCommandMemory, normalize_phrase


class VoiceCommandMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(Path(self.temporary.name))
        self.database.connect()
        self.database.create_tables()
        self.memory = VoiceCommandMemory(self.database)

    def tearDown(self) -> None:
        self.database.disconnect()
        self.temporary.cleanup()

    def test_normalization_ignores_accents_and_punctuation(self) -> None:
        self.assertEqual(normalize_phrase("¡ODÍN, vamos a casa!"), "vamos a casa")

    def test_remembers_resolves_confirms_and_forgets_per_commander(self) -> None:
        self.memory.remember("cmdr-a", "Llevame al rancho", "home_route", {})
        learned = self.memory.resolve("cmdr-a", "llevame al rancho")
        self.assertIsNotNone(learned)
        self.assertEqual(learned.intent, "home_route")
        self.assertIsNone(self.memory.resolve("cmdr-b", "llevame al rancho"))
        self.assertTrue(self.memory.confirm("cmdr-a", "Llevame al rancho"))
        self.assertTrue(self.memory.forget("cmdr-a", "Llevame al rancho"))
        self.assertIsNone(self.memory.resolve("cmdr-a", "Llevame al rancho"))

    def test_resolves_small_whisper_variation_but_rejects_ambiguity(self) -> None:
        self.memory.remember(
            "cmdr-a", "Bodín, déjame el rancho", "home_route", {}
        )
        learned = self.memory.resolve("cmdr-a", "debame el rancho")
        self.assertIsNotNone(learned)
        self.assertEqual(learned.intent, "home_route")
        self.assertIsNone(self.memory.resolve("cmdr-a", "vendeme el hierro"))


if __name__ == "__main__":
    unittest.main()
