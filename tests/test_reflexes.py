import unittest

from intelligence.reflexes import (
    ReflexResolver, is_trade_menu_request, normalize_command_transcription,
)


class ReflexResolverTests(unittest.TestCase):
    def test_routes_known_commands_without_language_model(self):
        resolver = ReflexResolver()
        examples = {
            "ODIN solicita atraque": ("docking_request", "HEIMDALL"),
            "ODIN vamos a casa": ("home_route", "HEIMDALL"),
            "quiero comerciar": ("freyja_trade_menu", "FREYJA"),
            "enciende visión nocturna": ("cockpit_night_vision", "HEIMDALL"),
        }
        for phrase, expected in examples.items():
            with self.subTest(phrase=phrase):
                match = resolver.resolve(phrase)
                self.assertIsNotNone(match)
                self.assertEqual((match.intent, match.officer), expected)

    def test_neutron_destination_is_structured(self):
        match = ReflexResolver().resolve(
            "calculá una ruta de neutrones hasta Colonia"
        )
        self.assertEqual(match.intent, "neutron_route")
        self.assertEqual(match.payload["destination"], "Colonia")

    def test_unknown_question_is_not_guessed(self):
        resolver = ReflexResolver()
        self.assertIsNone(resolver.resolve("contame algo interesante"))
        self.assertEqual(resolver.snapshot()["missed"], 1)

    def test_metrics_do_not_store_spoken_text(self):
        resolver = ReflexResolver()
        resolver.resolve("ODIN vamos a casa")
        snapshot = resolver.snapshot()
        self.assertEqual(snapshot["resolved"], 1)
        self.assertEqual(snapshot["by_intent"], {"home_route": 1})
        self.assertNotIn("ODIN vamos a casa", str(snapshot))

    def test_trade_aliases_remain_compatible(self):
        for phrase in ("quiero comerciar", "y gaseer comercio", "vale bien"):
            self.assertTrue(is_trade_menu_request(phrase))

    def test_observed_transcription_errors_resolve_safe_commands(self):
        examples = {
            "Odin solicita traque.": "docking_request",
            "o de intren de aterrizaje.": "cockpit_landing_gear",
            "Odin activó la visión nocturna.": "cockpit_night_vision",
            "Odin calculó una ruta de neutrones hasta Colonia.": "neutron_route",
        }
        resolver = ReflexResolver()
        for phrase, intent in examples.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(resolver.resolve(phrase).intent, intent)

    def test_normalizer_does_not_rewrite_unrelated_words(self):
        self.assertEqual(
            normalize_command_transcription("contame algo interesante"),
            "contame algo interesante",
        )


if __name__ == "__main__":
    unittest.main()
