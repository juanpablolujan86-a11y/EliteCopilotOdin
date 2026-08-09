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


if __name__ == "__main__":
    unittest.main()
