import unittest

from core.officer_names import public_officer_name, publicize_officer_text


class OfficerNameTests(unittest.TestCase):
    def test_navigation_keeps_internal_id_but_uses_njordr_publicly(self):
        self.assertEqual(public_officer_name("HEIMDALL"), "NJÖRÐR")

    def test_guardian_and_engineering_use_nordic_public_names(self):
        self.assertEqual(public_officer_name("GUARDIAN"), "HEIMDALL")
        self.assertEqual(public_officer_name("INGENIERÍA"), "VÖLUNDR")

    def test_public_text_distinguishes_navigation_from_guardian(self):
        self.assertEqual(
            publicize_officer_text("HEIMDALL trazó la ruta. GUARDIAN está listo."),
            "NJÖRÐR trazó la ruta. HEIMDALL está listo.",
        )

    def test_unknown_officer_is_preserved(self):
        self.assertEqual(public_officer_name("FREYJA"), "FREYJA")


if __name__ == "__main__":
    unittest.main()
