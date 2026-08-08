import tempfile
import unittest
from pathlib import Path

from core.database import DatabaseManager
from core.event_bus import EventBus
from core.expedition_ledger import ExpeditionLedger


class ExpeditionLedgerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(Path(self.temp.name))
        self.database.connect()
        self.database.create_tables()
        species = Path(__file__).parents[1] / "knowledge" / "biology" / "species.json"
        self.ledger = ExpeditionLedger(self.database, EventBus(), species)

    def tearDown(self) -> None:
        self.database.disconnect()
        self.temp.cleanup()

    def test_duplicate_scans_count_once_and_mapping_replaces_value(self) -> None:
        event = {
            "timestamp": "2026-01-01T00:00:00Z",
            "SystemAddress": 42,
            "StarSystem": "Prueba",
            "BodyID": 7,
            "BodyName": "Prueba 7",
            "PlanetClass": "Water world",
            "MassEM": 1.0,
            "TerraformState": "Terraformable",
            "WasDiscovered": False,
        }
        self.ledger.handle_fsd_jump(event)
        self.ledger.handle_scan(event)
        self.ledger.handle_scan(event)
        scan_value = self.ledger.summary().cartography_estimated
        event["EfficiencyBonus"] = True
        self.ledger._store_scan(event, mapped=True)
        summary = self.ledger.summary()

        self.assertEqual(summary.systems_visited, 1)
        self.assertEqual(summary.bodies_scanned, 1)
        self.assertGreater(summary.cartography_estimated, scan_value)

    def test_completed_organic_adds_base_and_first_logged_potential(self) -> None:
        self.database.execute(
            """
            INSERT INTO stellar_bodies
            (system_address, system_name, body_id, body_name, body_type,
             is_moon, terraformable, was_discovered, was_mapped,
             was_footfalled, landable, raw_json, scanned_at)
            VALUES (42, 'Prueba', 7, 'Prueba 7', 'Planeta', 0, 0, 0, 0, 0, 1, '{}', '')
            """
        )
        event = {
            "timestamp": "2026-01-01T00:00:00Z",
            "ScanType": "Analyse",
            "SystemAddress": 42,
            "Body": 7,
            "Species": "$Codex_Ent_Bacterial_05_Name;",
            "Species_Localised": "Bacteria vesicular",
            "Variant": "$Codex_Ent_Bacterial_05_Antimony_Name;",
            "Variant_Localised": "Bacteria vesicular - Cian",
        }
        self.ledger.handle_organic(event)
        self.ledger.handle_organic(event)
        summary = self.ledger.summary()

        self.assertEqual(summary.species_completed, 1)
        self.assertGreater(summary.exobiology_base, 0)
        self.assertEqual(summary.exobiology_potential, summary.exobiology_base * 5)

    def test_sales_are_confirmed_once_and_remove_pending_value(self) -> None:
        event = {
            "timestamp": "2026-01-01T00:00:00Z",
            "SystemAddress": 42,
            "StarSystem": "Prueba",
            "BodyID": 7,
            "BodyName": "Prueba 7",
            "PlanetClass": "Icy body",
            "MassEM": 1.0,
            "WasDiscovered": True,
        }
        self.ledger.handle_scan(event)
        sale = {
            "timestamp": "2026-01-02T00:00:00Z",
            "MarketID": 10,
            "TotalEarnings": 12345,
            "Discovered": [{"SystemName": "Prueba", "NumBodies": 1}],
        }
        self.ledger.handle_exploration_sale(sale)
        self.ledger.handle_exploration_sale(sale)
        summary = self.ledger.summary()

        self.assertEqual(summary.cartography_estimated, 0)
        self.assertEqual(summary.exploration_sold, 12345)

    def test_exploration_sale_clears_bodies_not_listed_as_discovered(self) -> None:
        for body_id, system in ((1, "Conocido"), (2, "Nuevo")):
            self.ledger.handle_scan({
                "timestamp": f"2026-01-01T00:00:0{body_id}Z",
                "SystemAddress": body_id,
                "StarSystem": system,
                "BodyID": body_id,
                "BodyName": f"{system} 1",
                "PlanetClass": "Icy body",
                "MassEM": 1.0,
                "WasDiscovered": system == "Conocido",
            })

        self.ledger.handle_exploration_sale({
            "timestamp": "2026-01-02T00:00:00Z",
            "MarketID": 10,
            "TotalEarnings": 2000,
            "Discovered": [{"SystemName": "Nuevo", "NumBodies": 1}],
        })

        self.assertEqual(self.ledger.summary().cartography_estimated, 0)

    def test_organic_sale_clears_pending_even_if_localised_name_differs(self) -> None:
        self.database.execute(
            """
            INSERT INTO stellar_bodies
            (system_address, system_name, body_id, body_name, body_type,
             is_moon, terraformable, was_discovered, was_mapped,
             was_footfalled, landable, raw_json, scanned_at)
            VALUES (42, 'Prueba', 7, 'Prueba 7', 'Planeta', 0, 0, 0, 0, 0, 1, '{}', '')
            """
        )
        self.ledger.handle_organic({
            "timestamp": "2026-01-01T00:00:00Z",
            "ScanType": "Analyse",
            "SystemAddress": 42,
            "Body": 7,
            "Species": "$Codex_Ent_Bacterial_05_Name;",
            "Species_Localised": "Bacteria vesicular",
            "Variant": "$Codex_Ent_Bacterial_05_Antimony_Name;",
            "Variant_Localised": "Bacteria vesicular - Cian",
        })

        self.ledger.handle_organic_sale({
            "timestamp": "2026-01-02T00:00:00Z",
            "MarketID": 10,
            "BioData": [{"Species_Localised": "Nombre diferente", "Value": 1}],
        })

        summary = self.ledger.summary()
        self.assertEqual(summary.exobiology_base, 0)
        self.assertEqual(summary.exobiology_potential, 0)
        self.assertEqual(summary.exobiology_sold, 1)


if __name__ == "__main__":
    unittest.main()
