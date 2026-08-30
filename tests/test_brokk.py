import json
import tempfile
import unittest
from pathlib import Path

from brokk.processor import MiningProcessor
from brokk.session import MiningSessionStore
from brokk.equipment import audit_mining_loadout


class BrokkMiningTests(unittest.TestCase):
    def test_complete_mining_loadout_enables_all_techniques(self):
        audit = audit_mining_loadout({
            "event": "Loadout", "Ship": "lakonminer", "CargoCapacity": 256,
            "Modules": [
                {"Item": "hpt_miningtoolv2_fixed_large"},
                {"Item": "hpt_mining_abrblstr_fixed_small"},
                {"Item": "hpt_mining_subsurfdispmisle_turret_medium"},
                {"Item": "hpt_mining_seismchrgwarhd_turret_medium"},
                {"Item": "hpt_mrascanner_size0_class4"},
                {"Item": "int_refinery_size3_class5"},
                {"Item": "int_multidronecontrol_miningv2_size5_class5"},
                {"Item": "int_cargorack_size6_class1"},
            ],
        })
        self.assertTrue(all(item.ready for item in audit.techniques.values()))
        self.assertEqual(audit.cargo_capacity, 256)
        self.assertEqual(audit.ship, "Type-11 Prospector")

    def test_incomplete_loadout_lists_missing_modules(self):
        audit = audit_mining_loadout({
            "event": "Loadout", "Ship": "sidewinder", "CargoCapacity": 4,
            "Modules": [{"Item": "int_cargorack_size1_class1"}],
        })
        self.assertFalse(audit.techniques["laser"].ready)
        self.assertIn("láser minero", audit.techniques["laser"].missing)
        self.assertIn("refinería", audit.techniques["laser"].missing)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "brokk" / "active_session.json"
        self.processor = MiningProcessor(MiningSessionStore(self.path))

    def tearDown(self):
        self.temporary.cleanup()

    def test_cargo_snapshot_tracks_real_hold_and_limpets(self):
        self.processor.handle({
            "event": "Cargo", "Vessel": "Ship", "Count": 208,
            "Inventory": [
                {"Name": "drones", "Name_Localised": "Dron", "Count": 208}
            ],
        })
        self.assertEqual(self.processor.session.cargo_count, 208)
        self.assertEqual(self.processor.session.limpets, 208)
        self.assertEqual(self.processor.session.cargo_inventory, {"Dron": 208})

    def test_count_only_cargo_event_preserves_detailed_inventory(self):
        self.processor.handle({
            "event": "Cargo", "Vessel": "Ship", "Count": 2,
            "Inventory": [{"Name": "painite", "Name_Localised": "Painita", "Count": 2}],
        })
        self.processor.handle({"event": "Cargo", "Vessel": "Ship", "Count": 1})
        self.assertEqual(self.processor.session.cargo_count, 1)
        self.assertEqual(self.processor.session.cargo_inventory, {"Painita": 2})

    def test_cargo_snapshot_separates_total_production_from_current_hold(self):
        for _ in range(3):
            self.processor.handle({
                "event": "MiningRefined", "Type_Localised": "Painita"
            })
        self.processor.handle({
            "event": "Cargo", "Vessel": "Ship", "Count": 2,
            "Inventory": [
                {"Name": "painite", "Name_Localised": "Painita", "Count": 2}
            ],
        })
        self.assertEqual(self.processor.session.produced, {"Painita": 3})
        self.assertEqual(self.processor.session.refined, {"Painita": 2})

    def test_transfer_to_carrier_removes_mined_cargo_without_selling(self):
        self.processor.handle({"event": "MiningRefined", "Type": "Platinum"})
        self.processor.handle({"event": "MiningRefined", "Type": "Platinum"})
        self.processor.handle({
            "event": "Cargo", "Vessel": "Ship", "Count": 2,
            "Inventory": [{"Name": "Platinum", "Count": 2}],
        })
        self.processor.handle({
            "event": "CargoTransfer",
            "Transfers": [
                {"Type": "Platinum", "Count": 2, "Direction": "tocarrier"}
            ],
        })
        self.assertEqual(self.processor.session.cargo_count, 0)
        self.assertEqual(self.processor.session.refined, {})
        self.assertEqual(
            self.processor.session.transferred_to_carrier, {"Platinum": 2}
        )
        self.assertEqual(self.processor.session.sale_revenue, 0)

    def test_prospect_starts_session_and_keeps_composition(self):
        self.processor.handle({
            "event": "ProspectedAsteroid", "Content": "$AsteroidMaterialContent_High;",
            "Remaining": 100.0,
            "Materials": [{"Name": "Platinum", "Proportion": 42.5}],
        })
        state = self.processor.session
        self.assertFalse(state.active)
        self.assertEqual(state.started_at, "")
        self.assertEqual(state.prospected_asteroids, 1)
        self.assertEqual(state.last_prospect["materials"][0], {
            "name": "Platinum", "proportion": 42.5,
        })

    def test_refined_units_are_not_duplicated_by_collected_cargo(self):
        for _ in range(3):
            self.processor.handle({"event": "MiningRefined", "Type": "Platinum"})
        self.processor.handle({"event": "CollectCargo", "Type": "Platinum"})
        self.assertEqual(self.processor.session.refined, {"Platinum": 3})

    def test_partial_sale_and_ejection_remove_only_available_mined_cargo(self):
        for _ in range(5):
            self.processor.handle({"event": "MiningRefined", "Type": "Platinum"})
        self.processor.handle({"event": "MarketSell", "Type": "Platinum", "Count": 2,
                               "SellPrice": 250000})
        self.processor.handle({"event": "EjectCargo", "Type": "Platinum", "Count": 1})
        self.assertEqual(self.processor.session.refined, {"Platinum": 2})
        self.assertEqual(self.processor.session.sold, {"Platinum": 2})
        self.assertEqual(self.processor.session.discarded, {"Platinum": 1})
        self.assertEqual(self.processor.session.sale_revenue, 500000)

    def test_complete_sale_closes_session_and_persists(self):
        self.processor.handle({"event": "MiningRefined", "Type": "Silver"})
        self.processor.handle({"event": "SupercruiseEntry"})
        self.processor.handle({"event": "MarketSell", "Type": "Silver", "Count": 1,
                               "SellPrice": 50000})
        restored = MiningProcessor(MiningSessionStore(self.path)).session
        self.assertFalse(restored.active)
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.sold, {"Silver": 1})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["sale_revenue"], 50000)

    def test_raw_engineering_materials_are_recorded(self):
        self.processor.handle({"event": "MaterialCollected", "Category": "Raw",
                               "Name": "iron", "Name_Localised": "Hierro", "Count": 3})
        self.processor.handle({"event": "MaterialCollected", "Category": "Encoded",
                               "Name": "irrelevant", "Count": 2})
        self.assertEqual(self.processor.session.engineering_materials, {"Hierro": 3})

    def test_session_can_pause_resume_and_keep_target(self):
        self.processor.start(system="Sol", technique="laser", target_mineral="Platino")
        self.assertFalse(self.processor.session.active)
        self.processor.handle({"event": "MiningRefined", "Type": "Platinum"})
        self.processor.pause()
        self.assertFalse(self.processor.session.active)
        self.assertEqual(self.processor.session.status, "paused")
        self.processor.start(target_mineral="Platino")
        self.assertTrue(self.processor.session.active)
        self.assertEqual(self.processor.session.status, "extracting")
        self.assertEqual(self.processor.session.target_mineral, "Platino")

    def test_new_session_resets_history_only_after_explicit_close(self):
        self.processor.start(system="Sol", target_mineral="Painita")
        self.processor.handle({"event": "MiningRefined", "Type": "Painite"})
        self.processor.close()
        self.assertEqual(self.processor.session.produced, {"Painite": 1})
        self.processor.start(system="LHS 20", target_mineral="Platino")
        self.assertEqual(self.processor.session.produced, {})
        self.assertEqual(self.processor.session.target_mineral, "Platino")
        self.assertEqual(self.processor.session.system, "LHS 20")

    def test_first_tonne_starts_and_supercruise_entry_ends_operation(self):
        self.processor.handle({
            "event": "ProspectedAsteroid",
            "Materials": [{"Name": "Platinum", "Proportion": 40.0}],
        })
        self.assertEqual(self.processor.session.started_at, "")
        self.processor.handle({"event": "MiningRefined", "Type": "Platinum"})
        self.assertTrue(self.processor.session.active)
        self.assertTrue(self.processor.session.started_at)
        self.processor.handle({"event": "SupercruiseEntry"})
        self.assertFalse(self.processor.session.active)
        self.assertEqual(self.processor.session.status, "completed")
        self.assertTrue(self.processor.session.ended_at)

    def test_advanced_technique_selected_by_commander_is_not_claimed_as_confirmed(self):
        self.processor.start(
            system="Sol", technique="subsurface",
            technique_source="commander", target_mineral="Tritio",
        )
        self.processor.handle({"event": "MiningRefined", "Type": "Tritium"})
        self.assertEqual(self.processor.session.technique, "subsurface")
        self.assertEqual(self.processor.session.technique_source, "commander")
        self.assertFalse(self.processor.session.technique_confirmed)

    def test_asteroid_cracked_confirms_deep_core_from_journal(self):
        self.processor.start(system="Sol", technique="abrasion")
        self.processor.handle({"event": "AsteroidCracked"})
        self.assertEqual(self.processor.session.technique, "core")
        self.assertEqual(self.processor.session.technique_source, "journal")
        self.assertTrue(self.processor.session.technique_confirmed)
        self.assertEqual(self.processor.session.cracked_asteroids, 1)

    def test_abrasion_virtual_operation_persists_and_closes_on_departure(self):
        self.processor.start(
            system="Col 285 Sector", body="Anillo A",
            technique="abrasion", target_mineral="Alejandrita",
        )
        self.processor.handle({
            "event": "ProspectedAsteroid", "Remaining": 75.0,
            "Materials": [{"Name": "Alexandrite", "Proportion": 18.4}],
        })
        self.processor.handle({
            "event": "MiningRefined", "Type_Localised": "Alejandrita",
        })
        active = MiningProcessor(MiningSessionStore(self.path)).session
        self.assertTrue(active.active)
        self.assertEqual(active.technique, "abrasion")
        self.assertEqual(active.produced, {"Alejandrita": 1})
        self.assertFalse(active.technique_confirmed)
        self.processor.handle({"event": "SupercruiseEntry"})
        closed = MiningProcessor(MiningSessionStore(self.path)).session
        self.assertEqual(closed.status, "completed")
        self.assertTrue(closed.ended_at)

    def test_subsurface_virtual_operation_tracks_multiple_refined_tonnes(self):
        self.processor.start(
            system="Borann", body="Borann A 2 Ring A",
            technique="subsurface", target_mineral="Tritio",
        )
        for _ in range(3):
            self.processor.handle({
                "event": "MiningRefined", "Type_Localised": "Tritio",
            })
        self.assertTrue(self.processor.session.active)
        self.assertEqual(self.processor.session.technique, "subsurface")
        self.assertEqual(self.processor.session.refined, {"Tritio": 3})
        self.assertEqual(self.processor.session.produced, {"Tritio": 3})

    def test_deep_core_virtual_operation_keeps_journal_confirmation_until_close(self):
        self.processor.start(
            system="GCRV 1568", body="Anillo B",
            technique="core", target_mineral="Ópalo del vacío",
        )
        self.processor.handle({"event": "AsteroidCracked"})
        self.processor.handle({
            "event": "MiningRefined", "Type_Localised": "Ópalo del vacío",
        })
        self.assertTrue(self.processor.session.active)
        self.assertEqual(self.processor.session.technique_source, "journal")
        self.assertTrue(self.processor.session.technique_confirmed)
        self.processor.handle({"event": "FSDJump", "StarSystem": "Destino"})
        restored = MiningProcessor(MiningSessionStore(self.path)).session
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.system, "Destino")
        self.assertTrue(restored.technique_confirmed)


if __name__ == "__main__":
    unittest.main()
