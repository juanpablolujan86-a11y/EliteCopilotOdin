import unittest
import tempfile
from pathlib import Path

from guardian.search import GuardianPlanStore, GuardianSearchClient


class GuardianSearchTests(unittest.TestCase):
    def test_successful_plan_is_persisted_and_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GuardianPlanStore(Path(directory) / "guardian" / "last_plan.json")
            store.save({
                "module_key": "fsd_booster", "collection": [{"system": "Synuefe"}],
                "broker": {"system": "Sol"}, "error": "", "status": "Listo",
            })
            restored = store.load()
            self.assertEqual(restored["module_key"], "fsd_booster")
            self.assertEqual(restored["collection"][0]["system"], "Synuefe")
            self.assertTrue(restored["restored"])

    def test_error_does_not_overwrite_successful_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "last_plan.json"
            store = GuardianPlanStore(path)
            store.save({"module_key": "fsd_booster", "error": "", "collection": []})
            original = path.read_text(encoding="utf-8")
            store.save({"module_key": "gauss_fixed_2", "error": "sin red"})
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_weapon_recipe_uses_weapon_blueprint_site(self):
        client = GuardianSearchClient()
        client._nearest_station = lambda *_args: None
        client._nearest_market = lambda *_args: None
        plan = client.plan({
            "category": "weapon",
            "requirements": [{
                "material": "guardian_weaponblueprint", "missing": 1,
            }],
        }, (758.0, -177.0, -133.0))
        self.assertEqual(plan["collection"][0]["system"], "Synuefe EU-Q c21-10")
        self.assertIn("arma", plan["collection"][0]["purpose"])

    def test_fighter_recipe_uses_vessel_blueprint_site(self):
        client = GuardianSearchClient()
        client._nearest_station = lambda *_args: None
        client._nearest_market = lambda *_args: None
        plan = client.plan({
            "category": "fighter",
            "requirements": [{
                "material": "guardian_vesselblueprint", "missing": 1,
            }],
        }, (754.0, -172.0, -138.0))
        self.assertEqual(plan["collection"][0]["system"], "Synuefe EU-Q c21-15")
        self.assertIn("nave", plan["collection"][0]["purpose"])

    def test_selects_nearest_guardian_module_site_locally(self):
        client = GuardianSearchClient()
        client._nearest_station = lambda *_args: None
        client._nearest_market = lambda *_args: None
        module = {"requirements": [{
            "material": "guardian_moduleblueprint", "missing": 1
        }]}

        result = client.plan(module, (860.125, -124.59375, -61.0625))

        self.assertEqual(result["collection"][0]["system"], "Synuefe NL-N c23-4")
        self.assertEqual(result["collection"][0]["location"], "Estructura Guardiana · B 3")
        self.assertEqual(result["collection"][0]["distance_ly"], 0.0)

    def test_distinguishes_guardian_broker_from_nanite_pylon_station(self):
        nanite = {"modules": [{"name": "Guardian Nanite Torpedo Pylon"}]}
        guardian = {"modules": [{"name": "Guardian Gauss Cannon"}]}
        self.assertFalse(GuardianSearchClient._is_guardian_broker(nanite))
        self.assertTrue(GuardianSearchClient._is_guardian_broker(guardian))

    def test_formats_industrial_material_trader(self):
        self.assertTrue(GuardianSearchClient._is_manufactured_trader({
            "primary_economy": "Industrial"
        }))
        self.assertFalse(GuardianSearchClient._is_manufactured_trader({
            "primary_economy": "High Tech"
        }))


if __name__ == "__main__":
    unittest.main()
