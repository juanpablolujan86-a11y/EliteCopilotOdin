import json
import logging
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
from mimir.galactic_region import find_region


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


def bacteria_scan() -> dict:
    return {
        "event": "Scan",
        "ScanType": "Detailed",
        "BodyName": "Hegai SS-K d8-4 B 2",
        "BodyID": 13,
        "SystemAddress": 149224998987,
        "StarSystem": "Hegai SS-K d8-4",
        "PlanetClass": "High metal content body",
        "AtmosphereType": "SulphurDioxide",
        "SurfaceGravity": 4.862442,
        "SurfaceTemperature": 337.126892,
        "SurfacePressure": 337.015808,
        "Volcanism": "",
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
                "atmosphere_composition": {},
                "materials": {},
                "orbital_period": None,
                "distance_from_arrival": None,
                "region_id": None,
                "region_name": None,
                "stars": [],
                "system_position": None,
                "body_types": [],
                "system_name": "",
            },
        )

    def test_real_system_region_is_sanguineous_rim(self) -> None:
        self.assertEqual(
            find_region(5344.6875, 194.46875, -2523.375),
            (34, "Sanguineous Rim"),
        )

    def test_dss_tussock_is_resolved_with_regional_context(self) -> None:
        event = {
            "event": "Scan",
            "BodyName": "Hegai ZL-D d12-5 4",
            "PlanetClass": "High metal content body",
            "AtmosphereType": "Ammonia",
            "AtmosphereComposition": [
                {"Name": "Ammonia", "Percent": 100.0}
            ],
            "SurfaceGravity": 2.235064,
            "SurfaceTemperature": 161.398331,
            "SurfacePressure": 238.103516,
            "Volcanism": "",
            "Landable": True,
        }
        planet = PlanetEventAdapter().from_scan_event(
            event,
            scientific_context={
                "region_id": 34,
                "region_name": "Sanguineous Rim",
                "stars": [{"type": "F", "luminosity": "Vb"}],
            },
        )
        predictions = self.officer.predict_species(
            planet,
            confirmed_genus_ids=(
                "$Codex_Ent_Tussocks_Genus_Name;",
            ),
        )

        self.assertEqual(
            [prediction.species.name for prediction in predictions],
            ["Tussock Divisa"],
        )

    def test_real_five_genus_dss_scan_keeps_every_confirmed_genus(self) -> None:
        event = {
            "event": "Scan",
            "BodyName": "Hegai ZL-D d12-5 4",
            "PlanetClass": "High metal content body",
            "AtmosphereType": "Ammonia",
            "AtmosphereComposition": [
                {"Name": "Ammonia", "Percent": 100.0}
            ],
            "SurfaceGravity": 2.235064,
            "SurfaceTemperature": 161.398331,
            "SurfacePressure": 238.103516,
            "Volcanism": "",
            "Landable": True,
            "WasDiscovered": False,
            "WasMapped": False,
            "WasFootfalled": False,
        }
        genus_ids = (
            "$Codex_Ent_Bacterial_Genus_Name;",
            "$Codex_Ent_Fungoids_Genus_Name;",
            "$Codex_Ent_Osseus_Genus_Name;",
            "$Codex_Ent_Shrubs_Genus_Name;",
            "$Codex_Ent_Tussocks_Genus_Name;",
        )
        genus_names = ("Bacteria", "Fungoida", "Osseus", "Frutexa", "Tusoc")
        context = {
            "region_id": 34,
            "region_name": "Sanguineous Rim",
            "stars": [{"type": "F", "luminosity": "Vb"}],
        }

        report = self.handler.handle_planet_scan(
            event,
            confirmed_genus_ids=genus_ids,
            confirmed_genus_names=genus_names,
            scientific_context=context,
        )

        self.assertIsNotNone(report)
        self.assertIn(
            "Género confirmado por DSS: Bacteria, Fungoida, Osseus, Frutexa, Tusoc",
            report.details,
        )
        self.assertTrue(any("Tussock Divisa" in item for item in report.details))
        self.assertIn("(×5)", report.message)

    def test_real_informem_variant_is_predicted_from_materials(self) -> None:
        event = {
            "event": "Scan",
            "BodyName": "Hegai YA-L c22-0 7",
            "PlanetClass": "Rocky ice body",
            "AtmosphereType": "Nitrogen",
            "SurfaceGravity": 3.09248,
            "SurfaceTemperature": 77.780975,
            "SurfacePressure": 969.983398,
            "Volcanism": "",
            "Materials": [
                {"Name": "polonium", "Percent": 0.493638}
            ],
        }
        planet = PlanetEventAdapter().from_scan_event(event)
        predictions = self.officer.predict_species(
            planet,
            confirmed_genus_ids=(
                "$Codex_Ent_Bacterial_Genus_Name;",
            ),
        )
        informem = next(
            prediction
            for prediction in predictions
            if prediction.species.name == "Bacterium Informem"
        )

        self.assertEqual(informem.variants, ("Lime",))

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

    def test_recommendation_lists_all_probable_samples(self) -> None:
        planet = PlanetEventAdapter().from_scan_event(
            tectonicas_scan()
        )

        recommendation = self.officer.analyze_planet(planet)

        self.assertIn(
            "Muestras biológicas probables:",
            recommendation.reasons,
        )
        self.assertTrue(
            any(
                "Stratum Tectonicas" in reason
                for reason in recommendation.reasons
            )
        )
        self.assertTrue(
            any(
                "Bacterium Aurasus" in reason
                for reason in recommendation.reasons
            )
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

    def test_confirmed_bacteria_filters_out_stratum(self) -> None:
        genus_id = "$Codex_Ent_Bacterial_Genus_Name;"
        planet = PlanetEventAdapter().from_scan_event(bacteria_scan())

        predictions = self.officer.predict_species(
            planet,
            confirmed_genus_ids=(genus_id,),
        )
        recommendation = self.officer.analyze_planet(
            planet,
            confirmed_genus_ids=(genus_id,),
        )
        report = self.handler.handle_planet_scan(
            bacteria_scan(),
            confirmed_genus_ids=(genus_id,),
            confirmed_genus_names=("Bacteria",),
        )

        self.assertEqual(
            {prediction.species.name for prediction in predictions},
            {"Bacterium Tela", "Bacterium Cerbrus"},
        )
        self.assertEqual(predictions[0].species.name, "Bacterium Tela")
        self.assertIn("1,949,000", recommendation.message)
        self.assertNotIn("Stratum", recommendation.message)
        self.assertIsNotNone(report)
        self.assertIn("Género confirmado por DSS: Bacteria", report.details)

    def test_confirmed_genus_without_species_is_explicit(self) -> None:
        report = self.handler.handle_planet_scan(
            bacteria_scan(),
            confirmed_genus_ids=(
                "$Codex_Ent_Bacterial_Genus_Name;",
                "$Codex_Ent_Tussocks_Genus_Name;",
            ),
            confirmed_genus_names=("Bacteria", "Tusoc"),
        )

        self.assertIsNotNone(report)
        self.assertIn(
            "Género confirmado con especie todavía indeterminada: Tusoc",
            report.details,
        )
        self.assertIn("DSS también confirmó Tusoc", report.message)

    def test_unfootfalled_planet_reports_first_logged_potential(self) -> None:
        event = tectonicas_scan() | {
            "Landable": True,
            "WasDiscovered": False,
            "WasMapped": False,
            "WasFootfalled": False,
        }

        report = self.handler.handle_planet_scan(event)

        self.assertIsNotNone(report)
        self.assertIn("primera pisada todavía está disponible", report.message)
        self.assertIn("100,054,000 créditos (×5)", report.message)
        self.assertTrue(
            any(
                "La bonificación First Logged es potencial" in detail
                for detail in report.details
            )
        )

    def test_prior_footfall_does_not_apply_first_logged_multiplier(self) -> None:
        event = tectonicas_scan() | {
            "Landable": True,
            "WasDiscovered": True,
            "WasMapped": True,
            "WasFootfalled": True,
        }

        report = self.handler.handle_planet_scan(event)

        self.assertIsNotNone(report)
        self.assertNotIn("(×5)", report.message)
        self.assertIn("Primera pisada reclamada: Sí", report.details)

    def test_planet_without_biology_remains_silent(self) -> None:
        event = {
            "event": "Scan",
            "BodyName": "Planeta sin biología compatible",
            "PlanetClass": "Icy body",
            "AtmosphereType": "None",
            "SurfaceGravity": 20.0,
            "SurfaceTemperature": 500.0,
            "Landable": True,
            "WasDiscovered": False,
            "WasMapped": False,
            "WasFootfalled": False,
        }

        report = self.handler.handle_planet_scan(event)

        self.assertIsNone(report)

    def test_subscriber_logs_silent_planet_evaluation(self) -> None:
        event_bus = EventBus()
        subscriber = MimirEventSubscriber(event_bus, self.handler)
        event = PlanetScanReady(
            event={
                "event": "Scan",
                "BodyName": "Planeta silencioso",
                "PlanetClass": "Icy body",
                "AtmosphereType": "None",
                "SurfaceGravity": 20.0,
                "SurfaceTemperature": 500.0,
            }
        )

        with self.assertLogs("mimir.activity", level=logging.INFO) as records:
            subscriber.handle_planet_scan(event)

        output = "\n".join(records.output)
        self.assertIn("EVALUACIÓN | cuerpo=Planeta silencioso", output)
        self.assertIn("sin interés biológico", output)

    def test_populated_system_suppresses_first_logged_estimate(self) -> None:
        event = tectonicas_scan() | {
            "Landable": True,
            "WasFootfalled": False,
        }

        report = self.handler.handle_planet_scan(
            event,
            system_population=1000,
        )

        self.assertIsNotNone(report)
        self.assertNotIn("(×5)", report.message)
        self.assertIn(
            "Sistema habitado: no se estima bonificación First Logged",
            report.details,
        )

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

    def test_mimir_supports_every_imported_bioscan_condition(self) -> None:
        condition_names = {
            condition
            for rule in self.rules_document["rules"]
            for condition in rule["conditions"]
        }

        self.assertEqual(
            condition_names - RuleEngine.SUPPORTED_CONDITIONS,
            set(),
        )


if __name__ == "__main__":
    unittest.main()
