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
