import unittest

from core.localization import priority_label
from core.version import CAPABILITY, VERSION


class LocalizationTestCase(unittest.TestCase):
    def test_internal_priorities_are_presented_in_spanish(self) -> None:
        self.assertEqual(priority_label("LOW"), "Baja")
        self.assertEqual(priority_label("MEDIUM"), "Media")
        self.assertEqual(priority_label("HIGH"), "Alta")
        self.assertEqual(priority_label("CRITICAL"), "Crítica")

    def test_unknown_priority_is_preserved(self) -> None:
        self.assertEqual(priority_label("UNKNOWN"), "UNKNOWN")

    def test_header_identifies_current_release(self) -> None:
        self.assertEqual(VERSION, "0.7.1")
        self.assertEqual(CAPABILITY, "MÍMIR y HEIMDALL consolidados")


if __name__ == "__main__":
    unittest.main()
