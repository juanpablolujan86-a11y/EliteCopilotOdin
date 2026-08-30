import unittest

from core.officer_names import public_officer_name


class OfficerNameTests(unittest.TestCase):
    def test_navigation_keeps_internal_id_but_uses_njordr_publicly(self):
        self.assertEqual(public_officer_name("HEIMDALL"), "NJÖRÐR")

    def test_guardian_and_engineering_use_nordic_public_names(self):
        self.assertEqual(public_officer_name("GUARDIAN"), "HEIMDALL")
        self.assertEqual(public_officer_name("INGENIERÍA"), "VÖLUNDR")

    def test_unknown_officer_is_preserved(self):
        self.assertEqual(public_officer_name("FREYJA"), "FREYJA")


if __name__ == "__main__":
    unittest.main()
