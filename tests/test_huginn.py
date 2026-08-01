import importlib.util
import json
import unittest
from pathlib import Path

from knowledge.engine import KnowledgeEngine
from knowledge.importer.biology_validator import (
    BiologyKnowledgeValidator,
)
from knowledge.importer.bioscan_biology_importer import (
    BioScanBiologyImporter,
)
from knowledge.importer.stratum_importer import StratumImporter


ROOT = Path(__file__).resolve().parents[1]
STRATUM_SOURCE = (
    ROOT
    / "knowledge"
    / "external"
    / "bioscan"
    / "EDMC-BioScan-master"
    / "src"
    / "bio_scan"
    / "bio_data"
    / "rulesets"
    / "stratum.py"
)
RULESETS_DIRECTORY = STRATUM_SOURCE.parent


def load_stratum_catalog() -> dict:
    specification = importlib.util.spec_from_file_location(
        "test_bioscan_stratum",
        STRATUM_SOURCE,
    )
    if specification is None or specification.loader is None:
        raise ImportError(f"No se pudo cargar {STRATUM_SOURCE}")

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.catalog


class HuginnTestCase(unittest.TestCase):
    def test_yggdrasil_imports_every_bioscan_catalog(self) -> None:
        importer = BioScanBiologyImporter(RULESETS_DIRECTORY)
        species, rules = importer.import_all()
        report = BiologyKnowledgeValidator().validate(species, rules)

        self.assertEqual(len(importer.source_files()), 19)
        self.assertEqual(report.genus_count, 19)
        self.assertEqual(report.species_count, 116)
        self.assertEqual(report.rules_count, 254)
        self.assertEqual(
            report.species_without_rules,
            ("stratum_aranaemus",),
        )
        self.assertEqual(report.duplicate_species_ids, ())
        self.assertEqual(report.duplicate_rule_ids, ())
        self.assertEqual(report.rules_without_species, ())
        self.assertEqual(report.empty_rule_ids, ())
        self.assertTrue(report.valid)

    def test_yggdrasil_output_matches_fresh_import(self) -> None:
        imported_species, imported_rules = BioScanBiologyImporter(
            RULESETS_DIRECTORY
        ).import_all()
        generated_species = json.loads(
            (ROOT / "knowledge" / "biology" / "species.json").read_text(
                encoding="utf-8"
            )
        )["species"]
        generated_rules = json.loads(
            (
                ROOT
                / "knowledge"
                / "biology"
                / "prediction_rules.json"
            ).read_text(encoding="utf-8")
        )["rules"]

        self.assertEqual(generated_species, imported_species)
        self.assertEqual(generated_rules, imported_rules)

    def test_stratum_import_is_complete_and_deterministic(self) -> None:
        species, rules = StratumImporter().convert(
            load_stratum_catalog()
        )

        self.assertEqual(len(species), 9)
        self.assertEqual(len(rules), 26)
        self.assertEqual(
            len({item["id"] for item in species}),
            len(species),
        )
        self.assertEqual(
            len({item["rule_id"] for item in rules}),
            len(rules),
        )

    def test_aranaemus_has_no_rules_in_source(self) -> None:
        species, rules = StratumImporter().convert(
            load_stratum_catalog()
        )

        self.assertIn(
            "stratum_aranaemus",
            {item["id"] for item in species},
        )
        self.assertNotIn(
            "stratum_aranaemus",
            {item["species"] for item in rules},
        )

    def test_knowledge_engine_loads_catalogs(self) -> None:
        engine = KnowledgeEngine()
        engine.load()

        self.assertTrue(engine.is_loaded())
        self.assertIn("biology", engine.get_domains())


if __name__ == "__main__":
    unittest.main()
