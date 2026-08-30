import json
import tempfile
import unittest
from pathlib import Path

from heimdall.fsd_specs import FSDModuleCatalog


class FSDModuleCatalogTests(unittest.TestCase):
    def test_resolves_normalized_journal_symbol_from_local_edmc_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "modules.json"
            path.write_text(json.dumps({
                "int_hyperdrive_size5_class5": {
                    "optmass": 1050, "maxfuel": 5,
                    "fuelmul": 0.012, "fuelpower": 2.45,
                }
            }), encoding="utf-8")
            catalog = FSDModuleCatalog((path,))

            spec = catalog.resolve("$Int_HyperDrive_Size5_Class5_Name;")

            self.assertEqual(spec.optimal_mass, 1050)
            self.assertEqual(spec.max_fuel_per_jump, 5)
            self.assertEqual(spec.fuel_multiplier, 0.012)
            self.assertEqual(spec.source, path.resolve())

    def test_missing_or_invalid_catalog_never_invents_constants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.json"
            self.assertIsNone(
                FSDModuleCatalog((missing,)).resolve("int_hyperdrive_size5_class5")
            )


if __name__ == "__main__":
    unittest.main()
