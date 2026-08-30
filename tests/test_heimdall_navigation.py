import json
import tempfile
import unittest
from pathlib import Path

from core.database import DatabaseManager
from heimdall.navigation import NavigationContextManager, RouteWaypoint
from heimdall.fsd_specs import FSDModuleCatalog


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

    def test_exact_plotter_readiness_never_hides_missing_physical_data(self) -> None:
        context = self.manager.context
        context.current_system = "Sol"
        context.fuel_capacity = 32
        context.reserve_capacity = 0.63
        context.unladen_mass = 400
        context.fsd_optimal_mass = 1800
        context.max_fuel_per_jump = 5

        incomplete = context.exact_plotter_readiness()
        self.assertFalse(incomplete["ready"])
        self.assertEqual(
            set(incomplete["missing"]), {"fuel_power", "fuel_multiplier"}
        )

        context.fsd_fuel_power = 2.0
        context.fsd_fuel_multiplier = 0.012
        self.assertTrue(context.exact_plotter_readiness()["ready"])

    def test_loadout_combines_edmc_base_constants_with_engineering_override(self) -> None:
        catalog_path = self.root / "modules.json"
        catalog_path.write_text(json.dumps({
            "int_hyperdrive_size5_class5": {
                "optmass": 1050, "maxfuel": 5,
                "fuelmul": 0.012, "fuelpower": 2.45,
            }
        }), encoding="utf-8")
        manager = NavigationContextManager(
            self.database, self.navroute, FSDModuleCatalog((catalog_path,))
        )
        manager.context.current_system = "Sol"

        manager.handle_event({
            "event": "Loadout", "UnladenMass": 400, "CargoCapacity": 64,
            "FuelCapacity": {"Main": 32, "Reserve": 0.63},
            "Modules": [{
                "Slot": "FrameShiftDrive", "Item": "int_hyperdrive_size5_class5",
                "Engineering": {"Modifiers": [
                    {"Label": "FSDOptimalMass", "Value": 1692.6},
                ]},
            }],
        })

        self.assertEqual(manager.context.fsd_optimal_mass, 1692.6)
        self.assertEqual(manager.context.fsd_fuel_power, 2.45)
        self.assertEqual(manager.context.fsd_fuel_multiplier, 0.012)
        self.assertTrue(manager.context.exact_plotter_readiness()["ready"])

    def test_exact_parameters_validate_cargo_and_use_complete_ship_physics(self) -> None:
        context = self.manager.context
        context.current_system = "Sol"
        context.cargo_capacity = 64
        context.fuel_capacity = 32
        context.reserve_capacity = 0.63
        context.fuel_reservoir = 0.4
        context.unladen_mass = 400
        context.fsd_optimal_mass = 1800
        context.max_fuel_per_jump = 5
        context.fsd_fuel_power = 2.0
        context.fsd_fuel_multiplier = 0.012
        context.fsd_range_boost = 10.5

        request = context.exact_plotter_parameters("Colonia", cargo=48)

        self.assertEqual(request["source"], "Sol")
        self.assertEqual(request["cargo"], 48)
        self.assertEqual(request["base_mass"], 400.63)
        self.assertEqual(request["range_boost"], 10.5)
        with self.assertRaisesRegex(ValueError, "capacidad"):
            context.exact_plotter_parameters("Colonia", cargo=65)

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

    def test_conventional_summary_uses_only_matching_real_game_route(self) -> None:
        self.manager.context.current_address = 10
        self.manager.context.route = (
            RouteWaypoint("Inicio", 10, (0.0, 0.0, 0.0), "K"),
            RouteWaypoint("Escala", 20, (3.0, 4.0, 0.0), "L"),
            RouteWaypoint("Final", 30, (3.0, 4.0, 12.0), "G"),
        )

        summary = self.manager.context.conventional_route_summary("Final")

        self.assertEqual(summary["total_jumps"], 2)
        self.assertEqual(summary["remaining_distance_ly"], 17.0)
        self.assertEqual(summary["scoopable_remaining"], 1)
        self.assertEqual(
            self.manager.context.conventional_route_summary("Otro destino"), {}
        )

    def test_fuel_assessment_finds_next_scoopable_star(self) -> None:
        self.manager.context.current_address = 1
        self.manager.context.fuel_main = 20.0
        self.manager.context.max_fuel_per_jump = 5.0
        self.manager.context.route = (
            RouteWaypoint("Actual", 1, (0.0, 0.0, 0.0), "M"),
            RouteWaypoint("Seca", 2, (1.0, 0.0, 0.0), "L"),
            RouteWaypoint("Repostaje", 3, (2.0, 0.0, 0.0), "K"),
        )

        fuel = self.manager.context.fuel_assessment()

        self.assertEqual(fuel.jumps_available, 4)
        self.assertEqual(fuel.jumps_to_refuel, 2)
        self.assertEqual(fuel.refuel_waypoint.system, "Repostaje")
        self.assertEqual(fuel.fuel_margin_t, 10.0)
        self.assertFalse(fuel.unsafe)

    def test_fuel_assessment_warns_if_conservative_range_is_insufficient(self) -> None:
        self.manager.context.current_address = 1
        self.manager.context.fuel_main = 9.0
        self.manager.context.max_fuel_per_jump = 5.0
        self.manager.context.route = (
            RouteWaypoint("Actual", 1, (0.0, 0.0, 0.0), "M"),
            RouteWaypoint("Seca", 2, (1.0, 0.0, 0.0), "T"),
            RouteWaypoint("Repostaje", 3, (2.0, 0.0, 0.0), "G"),
        )

        fuel = self.manager.context.fuel_assessment()

        self.assertTrue(fuel.unsafe)
        self.assertEqual(fuel.fuel_margin_t, -1.0)

    def test_fuel_assessment_accepts_reaching_final_non_scoopable_system(self) -> None:
        self.manager.context.current_address = 1
        self.manager.context.fuel_main = 10.0
        self.manager.context.max_fuel_per_jump = 5.0
        self.manager.context.route = (
            RouteWaypoint("Actual", 1, (0.0, 0.0, 0.0), "M"),
            RouteWaypoint("Final seca", 2, (1.0, 0.0, 0.0), "L"),
        )

        fuel = self.manager.context.fuel_assessment()

        self.assertTrue(fuel.destination_before_refuel)
        self.assertFalse(fuel.unsafe)
        self.assertIsNone(fuel.refuel_waypoint)

    def test_high_energy_route_finds_neutrons_and_white_dwarfs(self) -> None:
        self.manager.context.current_address = 1
        self.manager.context.route = (
            RouteWaypoint("Actual", 1, (0.0, 0.0, 0.0), "M"),
            RouteWaypoint("Enana", 2, (1.0, 0.0, 0.0), "DA"),
            RouteWaypoint("Neutrón", 3, (2.0, 0.0, 0.0), "N"),
            RouteWaypoint("Otro neutrón", 4, (3.0, 0.0, 0.0), "N"),
        )

        assessment = self.manager.context.high_energy_assessment()

        self.assertEqual(assessment.next_neutron.system, "Neutrón")
        self.assertEqual(assessment.jumps_to_next_neutron, 2)
        self.assertEqual(assessment.remaining_neutrons, 2)
        self.assertEqual(assessment.remaining_white_dwarfs, 1)

    def test_jet_cone_charge_is_consumed_by_boosted_jump(self) -> None:
        self.manager.handle_event({"event": "JetConeBoost", "BoostValue": 6.0})
        charged = self.manager.context.high_energy_assessment()
        self.assertTrue(charged.charged)
        self.assertEqual(charged.cone_exposures_session, 1)
        self.manager.handle_event({"event": "JetConeBoost", "BoostValue": 6.0})
        self.assertEqual(
            self.manager.context.high_energy_assessment().cone_exposures_session, 1
        )

        self.manager.handle_event({
            "event": "FSDJump", "StarSystem": "Destino", "SystemAddress": 2,
            "JumpDist": 366.8, "FuelUsed": 7.36, "FuelLevel": 110.0,
            "BoostUsed": 4,
        })
        used = self.manager.context.high_energy_assessment()

        self.assertFalse(used.charged)
        self.assertEqual(used.last_boost_used, 4)
        self.assertEqual(used.boosted_jumps_session, 1)
        self.assertEqual(self.manager.context.last_jump_distance, 366.8)

    def test_high_energy_guidance_uses_only_confirmed_event_stages(self) -> None:
        self.manager.context.target_star_class = "N"
        approach = self.manager.context.high_energy_guidance("FSDTarget")
        self.assertEqual(approach.stage, "approach")
        self.assertEqual(approach.star_type, "neutron")
        self.assertFalse(approach.charged)

        self.manager.handle_event({"event": "JetConeBoost", "BoostValue": 4.0})
        charged = self.manager.context.high_energy_guidance("JetConeBoost")
        self.assertEqual(charged.stage, "charged")
        self.assertTrue(charged.charged)

        self.manager.handle_event({
            "event": "FSDJump", "StarSystem": "Siguiente", "BoostUsed": 4,
        })
        complete = self.manager.context.high_energy_guidance("FSDJump")
        self.assertEqual(complete.stage, "boost_complete")
        self.assertFalse(complete.charged)

    def test_white_dwarf_guidance_is_always_a_warning(self) -> None:
        self.manager.context.target_star_class = "DA"

        guidance = self.manager.context.high_energy_guidance("FSDTarget")

        self.assertEqual(guidance.star_type, "white_dwarf")
        self.assertTrue(guidance.warning)

    def test_restore_does_not_duplicate_session_boost_counters(self) -> None:
        journal = self._journal([
            {"event": "JetConeBoost", "BoostValue": 6.0},
            {
                "event": "FSDJump", "StarSystem": "Destino",
                "SystemAddress": 2, "BoostUsed": 4,
            },
        ])
        self.manager.restore(journal)
        self.manager.restore(journal)

        assessment = self.manager.context.high_energy_assessment()
        self.assertEqual(assessment.cone_exposures_session, 1)
        self.assertEqual(assessment.boosted_jumps_session, 1)


if __name__ == "__main__":
    unittest.main()
