import tempfile
import unittest
from pathlib import Path

from core.database import DatabaseManager
from heimdall.navigation import NavigationContext
from heimdall.spansh import HeimdallRoutePlanner, SpanshClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payloads: list[dict]) -> None:
        self.headers = {}
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))


RESULT = {
    "job": "job-1",
    "source_system": "Origen",
    "destination_system": "Destino",
    "range": "66.12",
    "efficiency": "60",
    "total_jumps": 2,
    "distance": 400.0,
    "system_jumps": [
        {
            "system": "Origen", "id64": 1, "x": 0, "y": 0, "z": 0,
            "distance_jumped": 0, "distance_left": 400,
            "jumps": 0, "neutron_star": False,
        },
        {
            "system": "Neutrón", "id64": 2, "x": 100, "y": 0, "z": 0,
            "distance_jumped": 100, "distance_left": 300,
            "jumps": 1, "neutron_star": True,
        },
        {
            "system": "Destino", "id64": 3, "x": 400, "y": 0, "z": 0,
            "distance_jumped": 300, "distance_left": 0,
            "jumps": 1, "neutron_star": False,
        },
    ],
}


class SpanshRoutePlannerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(Path(self.temp.name))
        self.database.connect()
        self.database.create_tables()

    def tearDown(self) -> None:
        self.database.disconnect()
        self.temp.cleanup()

    def test_queued_job_is_polled_and_decoded(self) -> None:
        session = FakeSession([
            {"job": "job-1", "status": "queued"},
            {"status": "ok", "result": RESULT},
        ])
        client = SpanshClient(session, sleeper=lambda _: None)

        plan = client.plan_neutron_route("Origen", "Destino", 66.12)

        self.assertEqual(plan.total_jumps, 2)
        self.assertEqual(plan.next_waypoint.system, "Neutrón")
        self.assertTrue(plan.next_waypoint.neutron_star)
        self.assertIn("/results/job-1", session.calls[1][0])
        self.assertEqual(session.calls[0][1]["params"]["range"], 66.12)

    def test_planner_uses_live_context_and_persists_active_route(self) -> None:
        session = FakeSession([{"status": "ok", "result": RESULT}])
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(session, sleeper=lambda _: None),
            clipboard_writer=lambda _: None,
        )
        context = NavigationContext(
            current_system="Origen",
            max_jump_range=66.12,
        )

        plan = planner.plan_fastest(context, "Destino")
        saved = self.database.query(
            "SELECT * FROM heimdall_planned_routes WHERE status='active'"
        )

        self.assertEqual(plan.destination_system, "Destino")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["provider"], "Spansh")
        self.assertEqual(saved[0]["total_jumps"], 2)

    def test_background_calculation_does_not_touch_database_or_clipboard(self) -> None:
        copied = []
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(
                FakeSession([{"status": "ok", "result": RESULT}]),
                sleeper=lambda _: None,
            ),
            clipboard_writer=copied.append,
        )
        plan = planner.calculate_fastest(
            NavigationContext(current_system="Origen", max_jump_range=66.12),
            "Destino",
        )

        self.assertEqual(plan.destination_system, "Destino")
        self.assertEqual(copied, [])
        self.assertEqual(
            self.database.query(
                "SELECT COUNT(*) FROM heimdall_planned_routes WHERE status='active'"
            )[0][0],
            0,
        )

    def test_planner_requires_known_position_and_range(self) -> None:
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([])),
            clipboard_writer=lambda _: None,
        )
        with self.assertRaisesRegex(ValueError, "sistema actual"):
            planner.plan_fastest(NavigationContext(), "Destino")
        with self.assertRaisesRegex(ValueError, "alcance"):
            planner.plan_fastest(
                NavigationContext(current_system="Origen"),
                "Destino",
            )

    def test_route_copies_first_waypoint_then_advances_only_on_arrival(self) -> None:
        copied = []
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([{"status": "ok", "result": RESULT}])),
            clipboard_writer=copied.append,
        )
        context = NavigationContext(current_system="Origen", max_jump_range=66.12)

        planner.plan_fastest(context, "Destino")
        ignored = planner.advance_if_arrived("Salto intermedio")
        advanced = planner.advance_if_arrived("Neutrón")

        self.assertEqual(copied, ["Neutrón", "Destino"])
        self.assertIsNotNone(ignored)
        self.assertEqual(ignored.jumps_completed, 1)
        self.assertEqual(ignored.jumps_remaining, 1)
        self.assertEqual(advanced.copied_system, "Destino")
        self.assertFalse(advanced.route_complete)

    def test_repeated_jump_does_not_skip_waypoint_and_final_completes(self) -> None:
        copied = []
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([{"status": "ok", "result": RESULT}])),
            clipboard_writer=copied.append,
        )
        planner.plan_fastest(
            NavigationContext(current_system="Origen", max_jump_range=66.12),
            "Destino",
        )
        planner.advance_if_arrived("Neutrón")

        repeated = planner.advance_if_arrived("Neutrón")
        self.assertIsNotNone(repeated)
        completed = planner.advance_if_arrived("Destino")

        self.assertTrue(completed.route_complete)
        self.assertIsNone(completed.copied_system)
        rows = self.database.query(
            "SELECT status FROM heimdall_planned_routes ORDER BY id DESC LIMIT 1"
        )
        self.assertEqual(rows[0]["status"], "completed")

    def test_recalculated_game_route_abandons_stale_plan(self) -> None:
        copied = []
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([{"status": "ok", "result": RESULT}])),
            clipboard_writer=copied.append,
        )
        planner.plan_fastest(
            NavigationContext(current_system="Origen", max_jump_range=66.12),
            "Destino",
        )

        update = planner.advance_if_arrived(
            "Sistema alternativo",
            ["Sistema alternativo", "Nuevo destino"],
        )

        self.assertIsNotNone(update)
        self.assertTrue(update.route_abandoned)
        self.assertEqual(update.destination_system, "Destino")
        self.assertFalse(update.route_complete)
        self.assertIsNone(update.copied_system)
        rows = self.database.query(
            "SELECT status FROM heimdall_planned_routes ORDER BY id DESC LIMIT 1"
        )
        self.assertEqual(rows[0]["status"], "abandoned")

    def test_intermediate_jump_keeps_plan_when_waypoint_remains_in_game_route(self) -> None:
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([{"status": "ok", "result": RESULT}])),
            clipboard_writer=lambda _: None,
        )
        planner.plan_fastest(
            NavigationContext(current_system="Origen", max_jump_range=66.12),
            "Destino",
        )

        update = planner.advance_if_arrived(
            "Sistema intermedio",
            ["Sistema intermedio", "Neutrón", "Destino"],
        )

        self.assertIsNotNone(update)
        self.assertEqual(update.jumps_completed, 1)
        rows = self.database.query(
            "SELECT status FROM heimdall_planned_routes ORDER BY id DESC LIMIT 1"
        )
        self.assertEqual(rows[0]["status"], "active")

    def test_actual_jump_total_sums_conventional_segments(self) -> None:
        result = dict(RESULT)
        result["total_jumps"] = 2
        result["system_jumps"] = [dict(item) for item in RESULT["system_jumps"]]
        result["system_jumps"][1]["jumps"] = 4
        result["system_jumps"][2]["jumps"] = 3
        client = SpanshClient(
            FakeSession([{"status": "ok", "result": result}]),
            sleeper=lambda _: None,
        )

        plan = client.plan_neutron_route("Origen", "Destino", 66.12)

        self.assertEqual(plan.total_jumps, 7)
        self.assertEqual(plan.actual_total_jumps, 7)

    def test_compares_neutron_route_with_conservative_conventional_reference(self) -> None:
        plan = SpanshClient(
            FakeSession([{"status": "ok", "result": RESULT}]),
            sleeper=lambda _: None,
        ).plan_neutron_route("Origen", "Destino", 66.12)

        self.assertEqual(plan.conventional_minimum_jumps, 7)
        self.assertEqual(plan.estimated_jumps_saved, 5)
        self.assertTrue(plan.neutron_route_is_advantageous)

    def test_comparison_does_not_claim_savings_when_neutron_route_is_longer(self) -> None:
        result = dict(RESULT)
        result["distance"] = 100.0
        result["system_jumps"] = [dict(item) for item in RESULT["system_jumps"]]
        result["system_jumps"][1]["jumps"] = 2
        result["system_jumps"][2]["jumps"] = 2
        plan = SpanshClient(
            FakeSession([{"status": "ok", "result": result}]),
            sleeper=lambda _: None,
        ).plan_neutron_route("Origen", "Destino", 66.12)

        self.assertEqual(plan.conventional_minimum_jumps, 2)
        self.assertEqual(plan.estimated_jumps_saved, -2)
        self.assertFalse(plan.neutron_route_is_advantageous)

    def test_pending_waypoint_can_be_restored_without_advancing(self) -> None:
        copied = []
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([{"status": "ok", "result": RESULT}])),
            clipboard_writer=copied.append,
        )
        planner.plan_fastest(
            NavigationContext(current_system="Origen", max_jump_range=66.12),
            "Destino",
        )

        pending = planner.copy_pending_waypoint()

        self.assertEqual(pending, "Neutrón")
        self.assertEqual(copied, ["Neutrón", "Neutrón"])

    def test_active_route_snapshot_exposes_copy_fallback_data(self) -> None:
        planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(FakeSession([{"status": "ok", "result": RESULT}])),
            clipboard_writer=lambda _: None,
        )
        planner.plan_fastest(
            NavigationContext(current_system="Origen", max_jump_range=66.12),
            "Destino",
        )

        snapshot = planner.active_route_snapshot()

        self.assertEqual(snapshot["destination"], "Destino")
        self.assertEqual(snapshot["next_system"], "Neutrón")
        self.assertEqual(snapshot["remaining_jumps"], 2)
        self.assertEqual(snapshot["total_jumps"], 2)


if __name__ == "__main__":
    unittest.main()
