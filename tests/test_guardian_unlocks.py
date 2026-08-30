import unittest

from guardian.unlocks import GUARDIAN_MODULE_RECIPES, GuardianUnlockTracker


class GuardianUnlockTrackerTests(unittest.TestCase):
    def test_catalog_includes_modules_weapons_and_fighters(self):
        categories = {
            recipe.get("category", "module")
            for recipe in GUARDIAN_MODULE_RECIPES.values()
        }
        self.assertEqual(categories, {"module", "weapon", "fighter"})
        self.assertGreaterEqual(len(GUARDIAN_MODULE_RECIPES), 23)
        self.assertIn("gauss_fixed_2", GUARDIAN_MODULE_RECIPES)
        self.assertIn("fighter_lance", GUARDIAN_MODULE_RECIPES)

    def test_counts_materials_and_cargo_for_selected_unlock(self):
        tracker = GuardianUnlockTracker()
        tracker.handle({
            "event": "Materials",
            "Raw": [],
            "Manufactured": [
                {"Name": "guardian_powercell", "Count": 24},
                {"Name": "guardian_techcomponent", "Count": 6},
                {"Name": "focuscrystals", "Count": 24},
            ],
            "Encoded": [{"Name": "guardian_moduleblueprint", "Count": 2}],
        })
        tracker.handle({
            "event": "Cargo", "Inventory": [{"Name": "hnshockmount", "Count": 8}]
        })

        booster = tracker.snapshot()["modules"]["fsd_booster"]
        values = {item["material"]: item for item in booster["requirements"]}

        self.assertFalse(booster["complete"])
        self.assertEqual(values["guardian_techcomponent"]["missing"], 15)
        self.assertEqual(values["hnshockmount"]["missing"], 0)

    def test_live_collection_and_trade_update_counts(self):
        tracker = GuardianUnlockTracker()
        tracker.handle({"event": "MaterialCollected", "Name": "guardian_powercell", "Count": 3})
        tracker.handle({
            "event": "MaterialTrade",
            "Paid": {"Material": "guardian_powercell", "Quantity": 1},
            "Received": {"Material": "guardian_techcomponent", "Quantity": 2},
        })
        self.assertEqual(tracker.materials["guardian_powercell"], 2)
        self.assertEqual(tracker.materials["guardian_techcomponent"], 2)

    def test_market_cargo_is_removed_after_sale(self):
        tracker = GuardianUnlockTracker()
        tracker.handle({"event": "MarketBuy", "Type": "hnshockmount", "Count": 8})
        tracker.handle({"event": "MarketSell", "Type": "hnshockmount", "Count": 3})
        self.assertEqual(tracker.cargo["hnshockmount"], 5)


if __name__ == "__main__":
    unittest.main()
