import tempfile
import unittest
from pathlib import Path

from core.database import DatabaseManager
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

    def query(self, query, parameters=()):
        return []


class ExplorationProcessorTestCase(unittest.TestCase):
    def test_mimir_announces_system_with_only_stars_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            database = DatabaseManager(Path(folder))
            database.connect()
            database.create_tables()
            event_bus = EventBus()
            messages = []
            event_bus.subscribe(InternalEvent.VOICE_MESSAGE_READY, messages.append)
            processor = ExplorationProcessor(
                database,
                CommanderState(current_system="Estelar", system_address=42),
                event_bus,
            )
            processor.handle_fsd_jump({
                "event": "FSDJump", "StarSystem": "Estelar",
                "SystemAddress": 42, "timestamp": "inicio",
            })
            for body_id in (0, 1):
                processor.handle_scan({
                    "event": "Scan", "ScanType": "Detailed",
                    "StarSystem": "Estelar", "SystemAddress": 42,
                    "BodyID": body_id, "BodyName": f"Estelar {body_id}",
                    "StarType": "K", "timestamp": f"scan-{body_id}",
                })
            processor.handle_fss_discovery_scan({
                "event": "FSSDiscoveryScan", "SystemName": "Estelar",
                "SystemAddress": 42, "BodyCount": 2,
            })
            complete = {
                "event": "FSSAllBodiesFound", "SystemName": "Estelar",
                "SystemAddress": 42, "Count": 2,
            }
            processor.handle_fss_all_bodies_found(complete)
            processor.handle_fss_all_bodies_found(complete)

            star_only = [
                message for message in messages
                if message.reason == "Sistema compuesto solamente por estrellas"
            ]
            self.assertEqual(len(star_only), 1)
            self.assertIn("No hay planetas para escanear", star_only[0].message)
            database.disconnect()

    def test_mimir_does_not_announce_star_only_when_planet_exists(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            database = DatabaseManager(Path(folder))
            database.connect()
            database.create_tables()
            event_bus = EventBus()
            messages = []
            event_bus.subscribe(InternalEvent.VOICE_MESSAGE_READY, messages.append)
            processor = ExplorationProcessor(
                database,
                CommanderState(current_system="Mixto", system_address=7),
                event_bus,
            )
            processor.handle_fsd_jump({
                "event": "FSDJump", "StarSystem": "Mixto", "SystemAddress": 7,
            })
            processor.handle_scan({
                "event": "Scan", "StarSystem": "Mixto", "SystemAddress": 7,
                "BodyID": 0, "BodyName": "Mixto A", "StarType": "G",
            })
            processor.handle_scan({
                "event": "Scan", "StarSystem": "Mixto", "SystemAddress": 7,
                "BodyID": 1, "BodyName": "Mixto A 1", "PlanetClass": "Rocky body",
            })
            processor.handle_fss_all_bodies_found({
                "event": "FSSAllBodiesFound", "SystemName": "Mixto",
                "SystemAddress": 7, "Count": 2,
            })

            self.assertFalse(any(
                message.reason == "Sistema compuesto solamente por estrellas"
                for message in messages
            ))
            database.disconnect()

    def test_first_footfall_voice_message_is_confirmed_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            database = DatabaseManager(Path(folder))
            database.connect()
            database.create_tables()
            database.execute(
                """
                INSERT INTO stellar_bodies
                (system_address, system_name, body_id, body_name, body_type,
                 is_moon, terraformable, was_discovered, was_mapped,
                 was_footfalled, landable, raw_json, scanned_at)
                VALUES (42, 'Prueba', 7, 'Prueba 7', 'Planeta', 0, 0, 0, 0, 0, 1, '{}', '')
                """
            )
            event_bus = EventBus()
            messages = []
            event_bus.subscribe(InternalEvent.VOICE_MESSAGE_READY, messages.append)
            processor = ExplorationProcessor(
                database,
                CommanderState(system_address=42),
                event_bus,
            )
            event = {
                "event": "Disembark",
                "timestamp": "2026-01-01T00:00:00Z",
                "SystemAddress": 42,
                "BodyID": 7,
                "Body": "Prueba 7",
                "OnPlanet": True,
            }

            processor.handle_disembark(event)
            processor.handle_disembark(event)

            self.assertEqual(len(messages), 1)
            self.assertIn("mono pulgoso", messages[0].message)
            self.assertIn("Darwin", messages[0].message)
            self.assertEqual(messages[0].body_name, "Prueba 7")
            database.disconnect()

    def test_duplicate_all_bodies_found_report_is_ignored(self) -> None:
        database = FakeDatabase()
        processor = ExplorationProcessor(
            database,
            CommanderState(),
            EventBus(),
        )
        reports = []
        refreshes = []
        processor._refresh_system_totals = lambda *args: refreshes.append(args)
        processor._publish_report = lambda *args: reports.append(args)
        event = {
            "event": "FSSAllBodiesFound",
            "SystemAddress": 149224998987,
            "SystemName": "Hegai SS-K d8-4",
            "Count": 20,
        }

        processor.handle_fss_all_bodies_found(event)
        processor.handle_fss_all_bodies_found(event)

        self.assertEqual(len(reports), 1)
        self.assertEqual(len(refreshes), 1)

    def test_belt_cluster_is_not_registered_or_published(self) -> None:
        database = FakeDatabase()
        event_bus = EventBus()
        processor = ExplorationProcessor(
            database,
            CommanderState(),
            event_bus,
        )
        planet_events = []
        event_bus.subscribe(
            InternalEvent.PLANET_SCAN_READY,
            planet_events.append,
        )

        processor.handle_scan(
            {
                "event": "Scan",
                "ScanType": "AutoScan",
                "BodyName": "Hegai OM-M d7-2 A Belt Cluster 1",
                "BodyID": 2,
                "StarSystem": "Hegai OM-M d7-2",
                "SystemAddress": 80505522243,
                "Parents": [{"Ring": 1}, {"Star": 0}],
            }
        )

        self.assertEqual(database.executions, [])
        self.assertEqual(planet_events, [])

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

    def test_scan_persists_landable_and_first_footfall_flags(self) -> None:
        database = FakeDatabase()
        event_bus = EventBus()
        processor = ExplorationProcessor(
            database,
            CommanderState(),
            event_bus,
        )
        processor._refresh_system_totals = lambda *args: None

        event = bacteria_scan() | {
            "Landable": True,
            "WasDiscovered": False,
            "WasMapped": False,
            "WasFootfalled": False,
        }
        processor.handle_scan(event)

        insert_query, parameters = database.executions[0]
        self.assertIn("was_footfalled", insert_query)
        self.assertIn("landable", insert_query)
        self.assertEqual(parameters[-4:-2], (0, 1))

    def test_fss_body_signals_are_recorded_without_dss_genus(self) -> None:
        database = FakeDatabase()
        processor = ExplorationProcessor(
            database,
            CommanderState(),
            EventBus(),
        )
        processor._refresh_system_totals = lambda *args: None
        processor._publish_report = lambda *args: None

        processor.handle_saa_signals_found(
            {
                "event": "FSSBodySignals",
                "SystemAddress": 42,
                "BodyID": 7,
                "BodyName": "Test 1",
                "Signals": [
                    {
                        "Type": "$SAA_SignalType_Biological;",
                        "Type_Localised": "Biológica",
                        "Count": 3,
                    }
                ],
            }
        )

        self.assertTrue(
            any(
                "FSSBodySignals" in parameters
                for _, parameters in database.executions
            )
        )

        signal_insert = next(
            parameters
            for query, parameters in database.executions
            if "INSERT INTO biological_signals" in query
        )
        self.assertIn("Biological", signal_insert)

    def test_localized_biological_signal_is_accent_safe(self) -> None:
        self.assertTrue(
            ExplorationProcessor._is_biological_signal(
                {
                    "Type": "$SAA_SignalType_Biological;",
                    "Type_Localised": "Biológica",
                }
            )
        )
        self.assertFalse(
            ExplorationProcessor._is_biological_signal(
                {
                    "Type": "$SAA_SignalType_Geological;",
                    "Type_Localised": "Geológica",
                }
            )
        )

    def test_scan_organic_publishes_three_step_progress(self) -> None:
        database = FakeDatabase()
        event_bus = EventBus()
        processor = ExplorationProcessor(
            database,
            CommanderState(system_address=42),
            event_bus,
        )
        processor._refresh_system_totals = lambda *args: None
        processor._publish_report = lambda *args: None
        updates = []
        event_bus.subscribe(
            InternalEvent.ORGANIC_SCAN_UPDATED,
            updates.append,
        )

        processor.handle_scan_organic(
            {
                "event": "ScanOrganic",
                "Body": 7,
                "ScanType": "Analyse",
                "Species_Localised": "Concha Aureolas",
                "WasLogged": False,
            }
        )

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].progress, 3)
        self.assertTrue(updates[0].completed)
        self.assertFalse(updates[0].was_logged)

    def test_duplicate_organic_progress_is_silent(self) -> None:
        database = FakeDatabase()
        event_bus = EventBus()
        processor = ExplorationProcessor(
            database,
            CommanderState(system_address=42),
            event_bus,
        )
        refreshes = []
        reports = []
        processor._refresh_system_totals = lambda *args: refreshes.append(args)
        processor._publish_report = lambda *args: reports.append(args)
        updates = []
        event_bus.subscribe(
            InternalEvent.ORGANIC_SCAN_UPDATED,
            updates.append,
        )
        sample = {
            "event": "ScanOrganic",
            "Body": 7,
            "ScanType": "Sample",
            "Species": "$Codex_Ent_Bacterial_Informem_Name;",
            "Species_Localised": "Bacterium Informem",
            "Variant": "$Codex_Ent_Bacterial_Informem_Lime_Name;",
        }

        processor.handle_scan_organic(sample)
        processor.handle_scan_organic(sample)

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].progress, 2)
        self.assertEqual(refreshes, [])
        self.assertEqual(reports, [])


if __name__ == "__main__":
    unittest.main()
