import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from powerplay.assignments import (
    WeeklyAssignmentStore, assignment_from_text, assignment_search_request,
    assignment_solution, powerplay_cycle_id,
    classify_assignment,
)


class WeeklyAssignmentTests(unittest.TestCase):
    def test_classifies_common_weekly_assignment_families(self):
        self.assertEqual(classify_assignment("Escanea 11 megabuques"), "megaship")
        self.assertEqual(classify_assignment("Vende minerales extraídos"), "mining")
        self.assertEqual(classify_assignment("Entrega suministros de la potencia"), "transport")
        self.assertEqual(classify_assignment("Transfiere datos en un asentamiento"), "on_foot")

    def test_extracts_required_amount_from_visible_text(self):
        assignment = assignment_from_text("Escanea 11 megabuques")
        self.assertEqual(assignment.required, 11)
        self.assertEqual(assignment.source, "text")

    def test_reads_progress_counter_and_does_not_match_mining_inside_undermining(self):
        assignment = assignment_from_text(
            "Escanea meganaves en cualquier sistema undermining 0/12"
        )
        self.assertEqual(assignment.activity, "megaship")
        self.assertEqual(assignment.progress, 0)
        self.assertEqual(assignment.required, 12)

    def test_cycle_rolls_over_at_thursday_server_tick(self):
        before = datetime(2026, 8, 27, 6, 59, tzinfo=timezone.utc)
        after = datetime(2026, 8, 27, 7, 0, tzinfo=timezone.utc)
        self.assertEqual(powerplay_cycle_id(before), "2026-08-20")
        self.assertEqual(powerplay_cycle_id(after), "2026-08-27")

    def test_text_identity_changes_between_weekly_cycles(self):
        first = assignment_from_text(
            "Escanea 4 megabuques", cycle_id="2026-08-20"
        )
        second = assignment_from_text(
            "Escanea 4 megabuques", cycle_id="2026-08-27"
        )
        self.assertNotEqual(first.assignment_id, second.assignment_id)

    def test_persists_journal_assignment_and_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WeeklyAssignmentStore(Path(directory))
            assignment = store.ingest_mission({
                "event": "MissionAccepted", "MissionID": 42,
                "Name": "Mission_Powerplay_Scan",
                "LocalisedName": "Escanea 3 megabuques",
                "DestinationSystem": "Sol",
            })
            self.assertIsNotNone(assignment)
            self.assertTrue(store.complete("42"))
            restored = store.load()[0]
            self.assertEqual(restored.status, "completed")
            self.assertEqual(restored.progress, 3)

    def test_ignores_normal_missions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WeeklyAssignmentStore(Path(directory))
            self.assertIsNone(store.ingest_mission({
                "Name": "Mission_Courier", "MissionID": 9,
            }))

    def test_tracks_failure_abandonment_and_explicit_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WeeklyAssignmentStore(Path(directory))
            store.ingest_mission({
                "MissionID": 7, "Name": "Mission_Powerplay_Mining",
                "LocalisedName": "Extrae 20 minerales",
            })
            self.assertTrue(store.update_progress("7", 8))
            self.assertEqual(store.load()[0].progress, 8)
            self.assertTrue(store.set_status("7", "abandoned"))
            self.assertEqual(store.load()[0].status, "abandoned")

    def test_solution_explains_steps_and_existing_destination(self):
        assignment = assignment_from_text("Escanea 4 megabuques")
        assignment.destination_system = "Sol"
        solution = assignment_solution(assignment)
        self.assertEqual(solution["destination_system"], "Sol")
        self.assertFalse(solution["needs_location_search"])
        self.assertTrue(any("enlace de datos" in step for step in solution["steps"]))

    def test_search_request_maps_supported_activity(self):
        request = assignment_search_request(
            assignment_from_text("Destruye 12 naves enemigas")
        )
        self.assertTrue(request["eligible"])
        self.assertEqual(request["activity"], "combat")

    def test_search_request_does_not_invent_unspecified_mineral(self):
        request = assignment_search_request(
            assignment_from_text("Vende 40 minerales extraídos")
        )
        self.assertFalse(request["eligible"])
        self.assertEqual(request["activity"], "mining")


if __name__ == "__main__":
    unittest.main()
