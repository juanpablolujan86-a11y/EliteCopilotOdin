from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from core.command_center import CommandCenter
from core.localization import SUPPORTED_LANGUAGES, text
from heimdall.synthesis import FSDInjectionInventory
from mimir.context_registry import ScientificContextRegistry
from models.officer_report import OfficerReport
from voice.settings import VoiceSettingsRepository, apply_language_voice_preset


EXPECTED_INTENTS = {
    "trade": "freyja_trade_menu",
    "home": "home_route",
    "dock": "docking_request",
    "night": "cockpit_night_vision",
    "scoop": "cockpit_cargo_scoop",
    "gear": "cockpit_landing_gear",
    "jump": "cockpit_hyperspace",
}


class LanguageIntegrationTests(unittest.TestCase):
    def _verify_locale(self, language: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = VoiceSettingsRepository(root).load()
            apply_language_voice_preset(settings, language)
            self.assertTrue(settings.officers)
            self.assertTrue(all(item.provider == "edge" for item in settings.officers.values()))
            self.assertTrue(all(item.voice for item in settings.officers.values()))

            for command_key, expected_intent in EXPECTED_INTENTS.items():
                phrase = text(f"calibration.command.{command_key}", language)
                learned = CommandCenter._command_from_text(phrase)
                self.assertIsNotNone(learned, (language, command_key, phrase))
                self.assertEqual(learned.intent, expected_intent)

            report = OfficerReport(
                officer="MÍMIR", title="", message="", priority="HIGH",
                details=[], body_name="Sol A 1",
                probable_species=("Stratum Tectonicas",),
                probable_species_values=(("Stratum Tectonicas", 1, 5),),
                has_biological_signal=True,
            )
            alert = ScientificContextRegistry(language).record("Sol", report)
            self.assertIsNotNone(alert)
            self.assertIn("Stratum Tectonicas", alert.message)

            synthesis = FSDInjectionInventory(root / "materials.json", language=language)
            summary = synthesis.voice_summary()
            self.assertNotEqual(summary, text("fsd.summary", language))
            self.assertTrue(summary.strip())

    def test_es_419_integral_flow(self) -> None:
        self._verify_locale("es-419")

    def test_es_es_integral_flow(self) -> None:
        self._verify_locale("es-ES")

    def test_en_us_integral_flow(self) -> None:
        self._verify_locale("en-US")

    def test_en_gb_integral_flow(self) -> None:
        self._verify_locale("en-GB")

    def test_pt_br_integral_flow(self) -> None:
        self._verify_locale("pt-BR")

    def test_integral_suite_covers_every_supported_locale(self) -> None:
        self.assertEqual(
            set(SUPPORTED_LANGUAGES),
            {"es-419", "es-ES", "en-US", "en-GB", "pt-BR"},
        )
