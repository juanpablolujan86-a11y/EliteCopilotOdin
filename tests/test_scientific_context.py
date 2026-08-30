import unittest

from mimir.context_registry import ScientificContextRegistry
from models.officer_report import OfficerReport


def report(*species: str, signal: bool = True, body: str = "Prueba 2") -> OfficerReport:
    return OfficerReport(
        officer="MÍMIR", title="Predicción", message="", priority="HIGH",
        details=[], body_name=body, probable_species=species,
        probable_species_values=tuple((name, 1_000_000, 5_000_000) for name in species),
        has_biological_signal=signal,
    )


class ScientificContextTests(unittest.TestCase):
    def test_priority_alert_uses_selected_language(self) -> None:
        english = ScientificContextRegistry("en-US").record(
            "Sol", report("Stratum Tectonicas", body="Sol A 1")
        )
        portuguese = ScientificContextRegistry("pt-BR").record(
            "Sol", report("Recepta Umbrux", body="Sol A 2")
        )
        self.assertIn("may contain Stratum Tectonicas", english.message)
        self.assertIn("pode conter Recepta Umbrux", portuguese.message)

    def test_remembers_base_value_for_each_probable_species(self) -> None:
        registry = ScientificContextRegistry()
        registry.record("Sol", report("Bacterium Informem", body="Sol A 1"))

        self.assertEqual(
            registry.system_prediction_values("Sol"),
            {"Sol A 1": {"Bacterium Informem": 1_000_000}},
        )
        self.assertEqual(
            registry.system_prediction_rewards("Sol"),
            {"Sol A 1": {"Bacterium Informem": (1_000_000, 5_000_000)}},
        )

    def test_remembers_species_names_without_values(self) -> None:
        registry = ScientificContextRegistry()
        registry.record("Sistema", report("Bacterium Aurasus", "Stratum Tectonicas"))

        self.assertEqual(
            registry.system_predictions("Sistema")["Prueba 2"],
            ("Bacterium Aurasus", "Stratum Tectonicas"),
        )

    def test_tectonicas_alert_is_emitted_once_per_planet(self) -> None:
        registry = ScientificContextRegistry()
        first = registry.record(
            "Synuefua QF-L d9-25",
            report("Stratum Tectonicas", body="Synuefua QF-L d9-25 1"),
        )
        repeated = registry.record(
            "Synuefua QF-L d9-25",
            report("Stratum Tectonicas", body="Synuefua QF-L d9-25 1"),
        )

        self.assertIsNotNone(first)
        self.assertIn("Stratum Tectonicas", first.message)
        self.assertIn("planeta 1", first.message)
        self.assertNotIn("Synuefua", first.message)
        self.assertIsNone(repeated)

    def test_recepta_umbrux_uses_the_same_priority_alert(self) -> None:
        registry = ScientificContextRegistry()
        alert = registry.record(
            "Sistema",
            report("Recepta Umbrux", body="Sistema A 2"),
        )

        self.assertIsNotNone(alert)
        self.assertIn("Recepta Umbrux", alert.message)
        self.assertIn("planeta A 2", alert.message)

    def test_priority_species_share_one_alert_when_both_are_probable(self) -> None:
        registry = ScientificContextRegistry()
        alert = registry.record(
            "Sistema",
            report(
                "Recepta Umbrux",
                "Stratum Tectonicas",
                body="Sistema 3",
            ),
        )

        self.assertIsNotNone(alert)
        self.assertIn("Stratum Tectonicas y Recepta Umbrux", alert.message)
        self.assertIsNone(
            registry.record(
                "Sistema",
                report(
                    "Stratum Tectonicas",
                    "Recepta Umbrux",
                    body="Sistema 3",
                ),
            )
        )

    def test_priority_species_are_announced_on_independent_planets(self) -> None:
        registry = ScientificContextRegistry()

        tectonicas = registry.record(
            "Sistema",
            report("Stratum Tectonicas", body="Sistema 1"),
        )
        umbrux = registry.record(
            "Sistema",
            report("Recepta Umbrux", body="Sistema 4"),
        )

        self.assertIn("planeta 1", tectonicas.message)
        self.assertNotIn("Recepta Umbrux", tectonicas.message)
        self.assertIn("planeta 4", umbrux.message)
        self.assertNotIn("Stratum Tectonicas", umbrux.message)

    def test_no_alert_without_biological_signal_or_during_restore(self) -> None:
        registry = ScientificContextRegistry()
        self.assertIsNone(
            registry.record("Sistema", report("Stratum Tectonicas", signal=False))
        )
        self.assertIsNone(
            registry.record("Sistema", report("Stratum Tectonicas"), announce=False)
        )


if __name__ == "__main__":
    unittest.main()
