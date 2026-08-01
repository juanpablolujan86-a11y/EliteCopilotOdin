import json
import tempfile
import unittest
from pathlib import Path

from core.journal_reader import JournalReader
from core.processors.commander_state_updater import CommanderStateUpdater
from state.commander_state import CommanderState


class JournalBootstrapTestCase(unittest.TestCase):
    def test_current_system_is_restored_without_replaying_events(self) -> None:
        events = [
            {
                "timestamp": "2026-07-31T23:00:00Z",
                "event": "FSDJump",
                "StarSystem": "Sistema anterior",
                "SystemAddress": 1,
            },
            {
                "timestamp": "2026-08-01T00:54:00Z",
                "event": "FSDJump",
                "StarSystem": "Hegai SS-K d8-4",
                "SystemAddress": 149224998987,
                "Body": "Hegai SS-K d8-4 A",
                "FuelLevel": 119.08,
            },
            {
                "timestamp": "2026-08-01T01:02:02Z",
                "event": "Scan",
                "StarSystem": "Hegai SS-K d8-4",
                "SystemAddress": 149224998987,
                "BodyName": "Hegai SS-K d8-4 B 2",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "Journal.test.log"
            journal.write_text(
                "\n".join(json.dumps(event) for event in events),
                encoding="utf-8",
            )
            context = JournalReader(Path(directory)).current_system_context(
                journal
            )

        state = CommanderState()
        CommanderStateUpdater(state).restore_context(context)

        self.assertEqual(state.current_system, "Hegai SS-K d8-4")
        self.assertEqual(state.system_address, 149224998987)
        self.assertEqual(state.current_body, "Hegai SS-K d8-4 B 2")
        self.assertEqual(state.fuel_level, 119.08)
