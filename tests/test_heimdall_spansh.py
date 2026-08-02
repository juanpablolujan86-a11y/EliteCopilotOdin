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

    def test_planner_requires_known_position_and_range(self) -> None:
        planner = HeimdallRoutePlanner(self.database, SpanshClient(FakeSession([])))
        with self.assertRaisesRegex(ValueError, "sistema actual"):
            planner.plan_fastest(NavigationContext(), "Destino")
        with self.assertRaisesRegex(ValueError, "alcance"):
            planner.plan_fastest(
                NavigationContext(current_system="Origen"),
                "Destino",
            )


if __name__ == "__main__":
    unittest.main()
