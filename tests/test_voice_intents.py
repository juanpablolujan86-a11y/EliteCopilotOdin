import unittest

from intelligence.intents import parse_home_route_intent, parse_neutron_route_intent


class VoiceIntentTests(unittest.TestCase):
    def test_understands_base_and_home_aliases(self) -> None:
        self.assertIsNotNone(parse_home_route_intent("vamos a la base"))
        self.assertIsNotNone(parse_home_route_intent("ODIN vamos a casa"))
        self.assertIsNotNone(parse_home_route_intent("creá una ruta a la base"))
        self.assertIsNone(parse_home_route_intent("cuántas naves hay en la base"))

    def test_extracts_destination_after_neutron_route(self) -> None:
        intent = parse_neutron_route_intent(
            "calculá una ruta de neutrones hasta Flyua Drye PF-L d9-12"
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent.destination, "Flyua Drye PF-L d9-12")

    def test_extracts_destination_before_route_qualifier(self) -> None:
        intent = parse_neutron_route_intent(
            "quiero viajar a Diaguandri por la ruta de neutrones"
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent.destination, "Diaguandri")

    def test_does_not_execute_generic_or_unrelated_request(self) -> None:
        self.assertIsNone(parse_neutron_route_intent("cuántos saltos me faltan"))
        self.assertIsNone(
            parse_neutron_route_intent("calculá hasta algún sistema de la burbuja")
        )


if __name__ == "__main__":
    unittest.main()
