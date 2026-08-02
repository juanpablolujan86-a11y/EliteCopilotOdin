import unittest

from mimir.surface_navigation import SurfaceNavigationTracker


class SurfaceNavigationTrackerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = SurfaceNavigationTracker()
        self.tracker.update_status(
            {"Latitude": 0.0, "Longitude": 0.0, "PlanetRadius": 1_000_000.0}
        )

    def test_bacterium_requires_500_metres(self) -> None:
        update = self.tracker.record_sample(
            {
                "ScanType": "Log",
                "Genus": "$Codex_Ent_Bacterial_Genus_Name;",
                "Species": "$Codex_Ent_Bacterial_01_Name;",
            }
        )

        self.assertIsNotNone(update)
        self.assertEqual(update.progress, 1)
        self.assertEqual(update.required_distance_m, 500)
        self.assertFalse(update.ready_for_sample)

    def test_distance_becomes_ready_after_minimum_is_reached(self) -> None:
        self.tracker.record_sample(
            {
                "ScanType": "Log",
                "Genus": "$Codex_Ent_Bacterial_Genus_Name;",
                "Species": "$Codex_Ent_Bacterial_01_Name;",
            }
        )

        update = self.tracker.update_status(
            {"Latitude": 0.0, "Longitude": 0.03, "PlanetRadius": 1_000_000.0}
        )

        self.assertIsNotNone(update)
        self.assertEqual(update.distance_m, 500)
        self.assertTrue(update.ready_for_sample)

        farther = self.tracker.update_status(
            {"Latitude": 0.0, "Longitude": 0.05, "PlanetRadius": 1_000_000.0}
        )
        self.assertIsNone(farther)

    def test_updates_resume_if_commander_returns_inside_sample_radius(self) -> None:
        self.tracker.record_sample(
            {
                "ScanType": "Log",
                "Genus": "$Codex_Ent_Bacterial_Genus_Name;",
                "Species": "$Codex_Ent_Bacterial_01_Name;",
            }
        )
        self.tracker.update_status(
            {"Latitude": 0.0, "Longitude": 0.03, "PlanetRadius": 1_000_000.0}
        )

        update = self.tracker.update_status(
            {"Latitude": 0.0, "Longitude": 0.01, "PlanetRadius": 1_000_000.0}
        )

        self.assertIsNotNone(update)
        self.assertFalse(update.ready_for_sample)
        self.assertLess(update.distance_m, 500)

    def test_second_sample_uses_nearest_previous_location(self) -> None:
        event = {
            "Genus": "$Codex_Ent_Bacterial_Genus_Name;",
            "Species": "$Codex_Ent_Bacterial_01_Name;",
        }
        self.tracker.record_sample({**event, "ScanType": "Log"})
        self.tracker.update_status(
            {"Latitude": 0.0, "Longitude": 0.04, "PlanetRadius": 1_000_000.0}
        )
        update = self.tracker.record_sample({**event, "ScanType": "Sample"})

        self.assertEqual(update.progress, 2)
        self.assertAlmostEqual(update.distance_m, 0.0)
        self.assertEqual(len(self.tracker.sample_locations), 2)


if __name__ == "__main__":
    unittest.main()
