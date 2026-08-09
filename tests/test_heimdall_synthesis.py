from pathlib import Path
import tempfile
import unittest

from heimdall.synthesis import FSDInjectionInventory


class FSDInjectionInventoryTests(unittest.TestCase):
    def test_builds_all_three_grades_from_materials_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = FSDInjectionInventory(Path(directory) / "materials.json")
            inventory.handle({
                "event": "Materials",
                "Raw": [
                    {"Name": "carbon", "Count": 20},
                    {"Name": "vanadium", "Count": 8},
                    {"Name": "germanium", "Count": 10},
                    {"Name": "cadmium", "Count": 3},
                    {"Name": "niobium", "Count": 4},
                    {"Name": "arsenic", "Count": 2},
                    {"Name": "yttrium", "Count": 2},
                    {"Name": "polonium", "Count": 1},
                    {"Name": "iron", "Count": 100},
                ],
            })

            available = inventory.availability()
            self.assertEqual((available.basic, available.standard, available.premium), (8, 3, 1))
            self.assertNotIn("iron", inventory.materials)

    def test_collection_discard_and_synthesis_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "materials.json"
            inventory = FSDInjectionInventory(path)
            inventory.handle({"event": "MaterialCollected", "Name": "carbon", "Count": 4})
            inventory.handle({"event": "MaterialCollected", "Name": "vanadium", "Count": 3})
            inventory.handle({"event": "MaterialCollected", "Name": "germanium", "Count": 3})
            inventory.handle({"event": "MaterialDiscarded", "Name": "carbon", "Count": 1})
            inventory.handle({
                "event": "Synthesis",
                "Name": "FSDInjection_Basic",
                "Materials": [
                    {"Name": "carbon", "Count": 1},
                    {"Name": "vanadium", "Count": 1},
                    {"Name": "germanium", "Count": 1},
                ],
            })

            restored = FSDInjectionInventory(path)
            self.assertEqual(restored.materials["carbon"], 2)
            self.assertEqual(restored.availability().basic, 2)
            self.assertIn("2 inyecciones básicas", restored.voice_summary())
            self.assertIn("sin su autorización", restored.voice_summary())

    def test_material_trade_and_mission_reward_keep_inventory_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = FSDInjectionInventory(Path(directory) / "materials.json")
            inventory.handle({
                "event": "Materials",
                "Raw": [{"Name": "carbon", "Count": 10}],
            })
            inventory.handle({
                "event": "MaterialTrade",
                "Paid": {"Material": "carbon", "Quantity": 3},
                "Received": {"Material": "germanium", "Quantity": 1},
            })
            inventory.handle({
                "event": "MissionCompleted",
                "MaterialsReward": [{"Name": "vanadium", "Count": 2}],
            })

            self.assertEqual(inventory.materials["carbon"], 7)
            self.assertEqual(inventory.materials["germanium"], 1)
            self.assertEqual(inventory.materials["vanadium"], 2)
            self.assertEqual(inventory.availability().basic, 1)

    def test_recommends_lowest_available_grade_without_consuming_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = FSDInjectionInventory(Path(directory) / "materials.json")
            inventory.handle({
                "event": "Materials",
                "Raw": [
                    {"Name": "carbon", "Count": 5},
                    {"Name": "vanadium", "Count": 5},
                    {"Name": "germanium", "Count": 5},
                    {"Name": "cadmium", "Count": 5},
                    {"Name": "niobium", "Count": 5},
                ],
            })

            normal = inventory.recommend(60, 66.12)
            basic = inventory.recommend(80, 66.12)
            standard = inventory.recommend(95, 66.12)

            self.assertTrue(normal.already_reachable)
            self.assertEqual(basic.grade, "basic")
            self.assertTrue(basic.available)
            self.assertEqual(standard.grade, "standard")
            self.assertTrue(standard.available)
            self.assertEqual(inventory.materials["carbon"], 5)

    def test_reports_unavailable_grade_and_jump_beyond_premium(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = FSDInjectionInventory(Path(directory) / "materials.json")
            unavailable = inventory.recommendation_voice(90, 66.12)
            impossible = inventory.recommendation_voice(140, 66.12)

            self.assertIn("estándar", unavailable)
            self.assertIn("no hay materiales", unavailable)
            self.assertIn("supera incluso", impossible)
            self.assertIn("132.2", impossible)


if __name__ == "__main__":
    unittest.main()
