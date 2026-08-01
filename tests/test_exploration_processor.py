import unittest

from core.event_bus import EventBus
from core.internal_events import InternalEvent
from core.processors.exploration_processor import ExplorationProcessor
from state.commander_state import CommanderState
from tests.test_mimir import bacteria_scan


class FakeDatabase:
    def __init__(self) -> None:
        self.executions = []

    def execute(self, query, parameters=()) -> None:
        self.executions.append((query, parameters))


class ExplorationProcessorTestCase(unittest.TestCase):
    def test_dss_genus_is_propagated_to_following_planet_scan(self) -> None:
        database = FakeDatabase()
        event_bus = EventBus()
        processor = ExplorationProcessor(
            database,
            CommanderState(),
            event_bus,
        )
        processor._refresh_system_totals = lambda *args: None
        processor._publish_report = lambda *args: None
        planet_events = []
        event_bus.subscribe(
            InternalEvent.PLANET_SCAN_READY,
            planet_events.append,
        )

        processor.handle_saa_signals_found(
            {
                "event": "SAASignalsFound",
                "BodyName": "Hegai SS-K d8-4 B 2",
                "BodyID": 13,
                "SystemAddress": 149224998987,
                "Signals": [
                    {
                        "Type": "$SAA_SignalType_Biological;",
                        "Type_Localised": "Biológica",
                        "Count": 1,
                    }
                ],
                "Genuses": [
                    {
                        "Genus": "$Codex_Ent_Bacterial_Genus_Name;",
                        "Genus_Localised": "Bacteria",
                    }
                ],
            }
        )
        processor.handle_scan(bacteria_scan())

        self.assertEqual(len(planet_events), 1)
        self.assertEqual(
            planet_events[0].confirmed_genus_ids,
            ("$Codex_Ent_Bacterial_Genus_Name;",),
        )
        self.assertEqual(
            planet_events[0].confirmed_genus_names,
            ("Bacteria",),
        )
        self.assertTrue(
            any(
                "Bacteria" in parameters
                for _, parameters in database.executions
            )
        )


if __name__ == "__main__":
    unittest.main()
