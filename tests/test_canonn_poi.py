import json
import tempfile
import unittest
from pathlib import Path

from services.canonn_poi import CanonnPOICatalog, CanonnPOIError


class CanonnPOICatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_imports_json_persists_and_finds_nearest(self) -> None:
        source = self.root / "poi.json"
        source.write_text(json.dumps([
            {"Type": "Guardian", "System": "Lejano", "x": 90, "y": 0, "z": 0},
            {"Type": "Guardian", "System": "Cercano", "x": 3, "y": 4, "z": 0,
             "instructions": "Escanear la baliza"},
        ]), encoding="utf-8")
        catalog = CanonnPOICatalog(self.root)

        catalog.refresh(source)
        restored = CanonnPOICatalog(self.root)

        self.assertEqual(restored.nearest((0, 0, 0), limit=1)[0].system, "Cercano")
        self.assertEqual(restored.items[1].instructions, "Escanear la baliza")

    def test_imports_official_tsv_shape_case_insensitively(self) -> None:
        source = self.root / "poi.tsv"
        source.write_text(
            "Type\tSystem\tx\ty\tz\tinstructions\n"
            "ThargoidSites\tMerope\t-78.5\t-149.6\t-340.5\tVisitar sitio\n",
            encoding="utf-8",
        )

        items = CanonnPOICatalog(self.root).refresh(source)

        self.assertEqual(items[0].category, "ThargoidSites")
        self.assertAlmostEqual(items[0].x, -78.5)

    def test_finds_nearest_megaship_across_category_names(self) -> None:
        source = self.root / "megaships.json"
        source.write_text(json.dumps([
            {"Type": "Generation Megaship", "System": "Lejano",
             "x": 30, "y": 0, "z": 0},
            {"Type": "Megabuque abandonado", "System": "Cercano",
             "x": 3, "y": 4, "z": 0},
            {"Type": "Guardian", "System": "Ignorado",
             "x": 1, "y": 0, "z": 0},
        ]), encoding="utf-8")
        catalog = CanonnPOICatalog(self.root)
        catalog.refresh(source)

        matches = catalog.nearest_matching(
            (0, 0, 0), ("megaship", "megabuque"), limit=2,
        )

        self.assertEqual([item.system for item in matches], ["Cercano", "Lejano"])

    def test_invalid_refresh_preserves_previous_cache(self) -> None:
        valid = self.root / "valid.json"
        valid.write_text(json.dumps([
            {"Type": "Biology", "System": "A", "x": 1, "y": 2, "z": 3}
        ]), encoding="utf-8")
        invalid = self.root / "invalid.json"
        invalid.write_text('[{"Type":"Biology"}]', encoding="utf-8")
        catalog = CanonnPOICatalog(self.root)
        catalog.refresh(valid)

        with self.assertRaises(CanonnPOIError):
            catalog.refresh(invalid)

        self.assertEqual(catalog.items[0].system, "A")
        self.assertEqual(CanonnPOICatalog(self.root).items[0].system, "A")

    def test_rejects_non_https_remote_sources(self) -> None:
        with self.assertRaisesRegex(CanonnPOIError, "HTTPS"):
            CanonnPOICatalog(self.root).refresh("http://example.test/poi.json")

    def test_rejects_unsafe_record_url(self) -> None:
        source = self.root / "unsafe.json"
        source.write_text(json.dumps([
            {"Type": "Other", "System": "A", "x": 0, "y": 0, "z": 0,
             "url": "file:///secret.txt"}
        ]), encoding="utf-8")

        with self.assertRaisesRegex(CanonnPOIError, "URL no permitida"):
            CanonnPOICatalog(self.root).refresh(source)


if __name__ == "__main__":
    unittest.main()
