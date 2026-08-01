import json
import unittest
from pathlib import Path

from core.event_bus import EventBus
from core.internal_events import InternalEvent
from core.officer_dispatcher import OfficerDispatcher
from mimir.event_subscriber import MimirEventSubscriber
from mimir.officer_handler import MimirOfficerHandler
from mimir.planet_event_adapter import PlanetEventAdapter
from mimir.rule_engine import RuleEngine
from mimir.scientific_officer import ScientificOfficer
from models.events.planet_scan_ready import PlanetScanReady


ROOT = Path(__file__).resolve().parents[1]
SPECIES_FILE = ROOT / "knowledge" / "biology" / "species.json"
RULES_FILE = ROOT / "knowledge" / "biology" / "prediction_rules.json"


def tectonicas_scan() -> dict:
    return {
        "event": "Scan",
        "BodyName": "Planeta de prueba",
        "PlanetClass": "High metal content body",
        "AtmosphereType": "Carbon dioxide atmosphere",
        "SurfaceGravity": 3.138128,
        "SurfaceTemperature": 220.0,
        "SurfacePressure": 10_123.165625,
        "Volcanism": "No volcanism",
    }


class MimirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.officer = ScientificOfficer(
            species_file=SPECIES_FILE,
            rules_file=RULES_FILE,
        )
        self.handler = MimirOfficerHandler(self.officer)

    def test_planet_event_adapter_normalizes_scan(self) -> None:
        planet = PlanetEventAdapter().from_scan_event(
            tectonicas_scan()
        )

        self.assertEqual(
            planet,
            {
                "atmosphere": "CarbonDioxide",
                "body_type": "High metal content body",
                "gravity": 0.32,
                "temperature": 220.0,
                "volcanism": "None",
                "pressure": 0.1,
            },
        )

    def test_scientific_officer_recommends_tectonicas(self) -> None:
        planet = PlanetEventAdapter().from_scan_event(
            tectonicas_scan()
        )

        predictions = self.officer.predict_species(planet)
        recommendation = self.officer.analyze_planet(planet)

        self.assertEqual(len(predictions), 2)
        self.assertEqual(
            {prediction.species.name for prediction in predictions},
            {"Bacterium Aurasus", "Stratum Tectonicas"},
        )
        self.assertEqual(
            predictions[0].species.name,
            "Stratum Tectonicas",
        )
        self.assertEqual(recommendation.priority, "HIGH")
        self.assertEqual(
            recommendation.title,
            "Descenso científico recomendado",
        )

    def test_dispatcher_returns_mimir_report_for_scan_event(self) -> None:
        dispatcher = OfficerDispatcher()
        dispatcher.register(
            "planet_scan",
            self.handler.handle_planet_scan,
        )

        reports = dispatcher.dispatch(
            "planet_scan",
            tectonicas_scan(),
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].officer, "MÍMIR")
        self.assertEqual(reports[0].priority, "HIGH")

    def test_event_bus_publishes_scientific_report(self) -> None:
        event_bus = EventBus()
        reports = []
        MimirEventSubscriber(event_bus, self.handler)
        event_bus.subscribe(
            InternalEvent.SCIENTIFIC_ANALYSIS_READY,
            reports.append,
        )

        event_bus.publish_internal(
            InternalEvent.PLANET_SCAN_READY,
            PlanetScanReady(event=tectonicas_scan()),
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].officer, "MÍMIR")
        self.assertEqual(reports[0].priority, "HIGH")

    def test_non_planet_scan_is_ignored(self) -> None:
        report = self.handler.handle_planet_scan(
            {"event": "Scan", "StarType": "G"}
        )

        self.assertIsNone(report)

    def test_unknown_rule_condition_fails_closed(self) -> None:
        score, matches = RuleEngine().evaluate(
            {"atmosphere": "CarbonDioxide"},
            {
                "atmosphere": ["CarbonDioxide"],
                "parent_star": ["A"],
            },
        )

        self.assertEqual(score, 0)
        self.assertEqual(matches, [])

    def test_excluded_region_is_evaluated(self) -> None:
        engine = RuleEngine()
        rule = {"regions": ["!orion-cygnus-core"]}

        excluded_score, _ = engine.evaluate(
            {"region": "orion-cygnus-core"},
            rule,
        )
        allowed_score, _ = engine.evaluate(
            {"region": "sagittarius-carina"},
            rule,
        )

        self.assertEqual(excluded_score, 0)
        self.assertEqual(allowed_score, 100)

    def test_volcanism_list_uses_partial_matching(self) -> None:
        score, _ = RuleEngine().evaluate(
            {"volcanism": "minor silicate vapour geysers"},
            {"volcanism": ["metallic", "silicate", "rocky"]},
        )

        self.assertEqual(score, 100)

    def test_any_volcanism_requires_activity(self) -> None:
        engine = RuleEngine()

        inactive_score, _ = engine.evaluate(
            {"volcanism": "None"},
            {"volcanism": "Any"},
        )
        active_score, _ = engine.evaluate(
            {"volcanism": "water geysers"},
            {"volcanism": "Any"},
        )

        self.assertEqual(inactive_score, 0)
        self.assertEqual(active_score, 100)


class BiologyKnowledgeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.species_document = json.loads(
            SPECIES_FILE.read_text(encoding="utf-8")
        )
        cls.rules_document = json.loads(
            RULES_FILE.read_text(encoding="utf-8")
        )

    def test_knowledge_ids_are_unique_and_references_are_valid(self) -> None:
        species_ids = [
            item["id"]
            for item in self.species_document["species"]
        ]
        rule_ids = [
            item["rule_id"]
            for item in self.rules_document["rules"]
        ]
        referenced_species = {
            item["species"]
            for item in self.rules_document["rules"]
        }

        self.assertEqual(len(species_ids), len(set(species_ids)))
        self.assertEqual(len(rule_ids), len(set(rule_ids)))
        self.assertLessEqual(referenced_species, set(species_ids))

    def test_aranaemus_is_known_but_not_predictable(self) -> None:
        species_by_id = {
            item["id"]: item
            for item in self.species_document["species"]
        }
        referenced_species = {
            item["species"]
            for item in self.rules_document["rules"]
        }

        self.assertIn("stratum_aranaemus", species_by_id)
        self.assertNotIn("stratum_aranaemus", referenced_species)


if __name__ == "__main__":
    unittest.main()
