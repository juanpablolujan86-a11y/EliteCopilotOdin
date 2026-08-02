import json
import tempfile
import unittest
from pathlib import Path

from core.database import DatabaseManager
from heimdall.navigation import NavigationContextManager, RouteWaypoint


class NavigationContextManagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = DatabaseManager(self.root / "data")
        self.database.connect()
        self.database.create_tables()
        self.navroute = self.root / "NavRoute.json"
        self.manager = NavigationContextManager(self.database, self.navroute)

    def tearDown(self) -> None:
        self.database.disconnect()
        self.temp.cleanup()

    def _journal(self, events: list[dict]) -> Path:
        path = self.root / "Journal.test.log"
        path.write_text(
            "\n".join(json.dumps(event) for event in events) + "\n",
            encoding="utf-8",
        )
        return path

    def test_restore_replays_fuel_events_in_chronological_order(self) -> None:
        journal = self._journal([
            {
                "event": "Loadout", "Ship": "explorer_nx", "ShipID": 30,
                "ShipName": "ODIN", "ShipIdent": "ZO-05E",
                "MaxJumpRange": 66.12,
                "FuelCapacity": {"Main": 128, "Reserve": 1.14},
                "Modules": [{
                    "Slot": "FrameShiftDrive", "Item": "fsd_sco",
                    "Health": 0.958,
                    "Engineering": {
                        "Engineer": "Felicity Farseer",
                        "BlueprintName": "LongRange", "Level": 5,
                        "Modifiers": [{"Label": "MaxFuelPerJump", "Value": 7.48}],
                    },
                }],
            },
            {"event": "FuelScoop", "Total": 127.0},
            {
                "event": "FSDJump", "StarSystem": "Destino",
                "SystemAddress": 42, "StarPos": [1, 2, 3], "FuelLevel": 120.0,
            },
        ])

        context = self.manager.restore(journal)

        self.assertEqual(context.fuel_main, 120.0)
        self.assertEqual(context.current_system, "Destino")
        self.assertEqual(context.current_position, (1.0, 2.0, 3.0))
        self.assertEqual(context.max_fuel_per_jump, 7.48)
        self.assertEqual(context.conservative_jumps_available, 16)

    def test_reads_route_and_classifies_scoopable_stars(self) -> None:
        self.navroute.write_text(json.dumps({"Route": [
            {
                "StarSystem": "KGBFOAM", "SystemAddress": 1,
                "StarPos": [4, 5, 6], "StarClass": "K",
            },
            {
                "StarSystem": "Seca", "SystemAddress": 2,
                "StarPos": [7, 8, 9], "StarClass": "L",
            },
        ]}), encoding="utf-8")

        self.assertTrue(self.manager.poll_route())
        self.assertTrue(self.manager.context.route[0].scoopable)
        self.assertFalse(self.manager.context.route[1].scoopable)

    def test_persists_status_and_route_with_tuple_positions(self) -> None:
        self.manager.context.route = (
            RouteWaypoint("Sistema", 7, (1.0, 2.0, 3.0), "M"),
        )
        self.manager.update_status({
            "Fuel": {"FuelMain": 32.5, "FuelReservoir": 0.8},
            "Destination": {"System": 7, "Name": "Sistema"},
        })

        restored = NavigationContextManager(self.database, self.navroute)
        restored._load_saved(json.loads(self.database.query(
            "SELECT json FROM heimdall_navigation_state WHERE id=1"
        )[0]["json"]))

        self.assertEqual(restored.context.fuel_main, 32.5)
        self.assertEqual(restored.context.target_system, "Sistema")
        self.assertEqual(restored.context.route[0].position, (1.0, 2.0, 3.0))

    def test_route_progress_starts_at_current_system(self) -> None:
        self.manager.context.current_address = 2
        self.manager.context.route = (
            RouteWaypoint("Recorrido", 1, (0.0, 0.0, 0.0), "M"),
            RouteWaypoint("Actual", 2, (3.0, 0.0, 0.0), "K"),
            RouteWaypoint("Siguiente", 3, (6.0, 4.0, 0.0), "L"),
            RouteWaypoint("Final", 4, (6.0, 4.0, 12.0), "G"),
        )

        progress = self.manager.context.route_progress()

        self.assertEqual(progress.completed_jumps, 1)
        self.assertEqual(progress.remaining_jumps, 2)
        self.assertEqual(progress.remaining_distance_ly, 17.0)
        self.assertEqual(progress.next_waypoint.system, "Siguiente")
        self.assertFalse(progress.off_route)

    def test_route_progress_detects_deviation_without_false_empty_route_alarm(self) -> None:
        empty = self.manager.context.route_progress()
        self.assertFalse(empty.off_route)

        self.manager.context.current_system = "Sistema ajeno"
        self.manager.context.route = (
            RouteWaypoint("Ruta", 10, (0.0, 0.0, 0.0), "M"),
        )
        deviated = self.manager.context.route_progress()

        self.assertTrue(deviated.off_route)
        self.assertIsNone(deviated.remaining_jumps)

    def test_route_progress_marks_destination_complete(self) -> None:
        self.manager.context.current_address = 20
        self.manager.context.route = (
            RouteWaypoint("Inicio", 10, (0.0, 0.0, 0.0), "M"),
            RouteWaypoint("Final", 20, (1.0, 0.0, 0.0), "G"),
        )

        progress = self.manager.context.route_progress()

        self.assertTrue(progress.route_complete)
        self.assertEqual(progress.remaining_jumps, 0)
        self.assertIsNone(progress.next_waypoint)


if __name__ == "__main__":
    unittest.main()
