import unittest
import tempfile
import threading
from pathlib import Path

from core.localization import (
    SUPPORTED_LANGUAGES, normalize_language, priority_label, text,
)
from core.version import CAPABILITY, VERSION
from core.config import Config
from main import configure_language
from voice.settings import VoiceSettingsRepository


class LocalizationTestCase(unittest.TestCase):
    def test_internal_priorities_are_presented_in_spanish(self) -> None:
        self.assertEqual(priority_label("LOW"), "Baja")
        self.assertEqual(priority_label("MEDIUM"), "Media")
        self.assertEqual(priority_label("HIGH"), "Alta")
        self.assertEqual(priority_label("CRITICAL"), "Crítica")

    def test_unknown_priority_is_preserved(self) -> None:
        self.assertEqual(priority_label("UNKNOWN"), "UNKNOWN")

    def test_supported_languages_are_stable_installer_codes(self) -> None:
        self.assertEqual(
            tuple(SUPPORTED_LANGUAGES),
            ("es-419", "es-ES", "en-US", "en-GB", "pt-BR"),
        )
        self.assertEqual(normalize_language("es-MX"), "es-419")
        self.assertEqual(normalize_language("unknown"), "es-419")

    def test_priority_and_shared_text_use_selected_language(self) -> None:
        self.assertEqual(priority_label("HIGH", "en-US"), "High")
        self.assertEqual(priority_label("MEDIUM", "pt-BR"), "Média")
        self.assertEqual(text("settings.language", "en-GB"), "ODIN LANGUAGE")

    def test_main_window_catalog_is_complete_for_every_language(self) -> None:
        keys = (
            "app.title", "app.command_center", "app.initializing", "app.settings",
            "app.operational_log", "app.live", "app.commander_ship",
            "app.credits", "app.expedition", "app.cartography", "app.exobiology",
            "common.calculate", "common.copy", "heimdall.neutron_route",
            "heimdall.calculate_neutron", "heimdall.calculate_exact",
            "heimdall.exact_active",
            "heimdall.high_energy", "heimdall.cone_state_charged",
            "heimdall.cone_state_neutron", "heimdall.cone_state_white_dwarf",
            "heimdall.cone_state_idle",
            "heimdall.next_leg", "heimdall.exact_leg",
            "heimdall.refuel_required", "heimdall.scoop_available",
            "heimdall.no_refuel_required",
            "heimdall.next_system", "heimdall.no_route", "mimir.summary",
            "heimdall.route_comparison", "heimdall.route_comparison_exact",
            "heimdall.route_comparison_waiting",
            "heimdall.exact_plotter", "heimdall.exact_ready",
            "heimdall.exact_missing",
            "mimir.biological_planets", "mimir.sample_tracking",
            "freyja.choose_model", "freyja.commodity", "freyja.include_planetary",
            "freyja.powerplay_sale", "freyja.quick", "freyja.three",
            "freyja.expedition", "freyja.powerplay", "freyja.status",
            "freyja.strategy", "freyja.product", "freyja.next_target",
            "freyja.tons", "freyja.estimated_profit", "freyja.unit_price",
            "freyja.distance", "freyja.powerplay_territory",
            "freyja.realized_profit",
            "freyja.no_route", "freyja.no_strategy", "common.no_data",
            "units.light_years",
            "powerplay.choose_activity", "powerplay.combat", "powerplay.trade",
            "powerplay.mining", "powerplay.transport", "powerplay.exploration",
            "powerplay.on_foot", "powerplay.salvage", "powerplay.power",
            "powerplay.rank", "powerplay.merits", "powerplay.earned",
            "powerplay.territory", "powerplay.activity", "powerplay.locations",
            "powerplay.use_heimdall", "powerplay.searching_combat",
            "powerplay.no_activity", "powerplay.verification.direct",
            "powerplay.verification.contextual", "powerplay.verification.experimental",
            "powerplay.verification.unverified", "powerplay.operation.reinforce",
            "powerplay.operation.undermine", "powerplay.operation.acquire",
            "canonn.section", "canonn.source", "canonn.update", "canonn.help",
            "canonn.source_required", "canonn.updated", "canonn.updating",
            "powerplay.guidance.combat", "powerplay.guidance.trade",
            "powerplay.guidance.mining", "powerplay.guidance.transport",
            "powerplay.guidance.exploration", "powerplay.guidance.on_foot",
            "powerplay.guidance.salvage",
            "powerplay.subject",
            "powerplay.contact_unverified",
            "powerplay.open_weekly_guide", "powerplay.weekly_guide_title",
            "powerplay.weekly_guide_intro",
            "brokk.operation", "brokk.technique", "brokk.technique.laser",
            "brokk.technique.abrasion", "brokk.technique.subsurface",
            "brokk.technique.core", "brokk.prepare", "brokk.search_mine",
            "brokk.search_hint", "brokk.short", "brokk.medium", "brokk.long",
            "dashboard.mining.paused", "dashboard.mining.completed",
            "brokk.limpets", "brokk.consulting_prices",
            "brokk.confirmed_per_hour", "brokk.estimated_cargo",
            "brokk.sold_value", "brokk.no_refined", "brokk.no_materials",
            "network.active", "network.inactive", "network.waiting",
            "guardian.search_failed", "settings.saved_log",
            "calibration.deleted_log", "footer.ptt", "footer.wake",
            "footer.docking", "footer.journal", "brokk.no_prospects",
            "brokk.reserve_remaining", "common.unknown",
            "brokk.waiting_equipment", "brokk.unknown_ship",
            "brokk.ship_hold", "brokk.equipment_ready",
            "brokk.equipment_missing",
            "settings.bindings_backup", "settings.no_snapshots",
            "settings.restore_bindings", "settings.bindings_restore_help",
            "settings.restore_bindings_confirm", "settings.restore_bindings_done",
            "brokk.no_result", "brokk.route", "brokk.pause", "brokk.close",
            "brokk.search_sale", "brokk.target", "brokk.location",
            "brokk.prospected", "brokk.cargo", "brokk.performance",
            "brokk.sale_target", "brokk.sale_demand", "brokk.global_sale",
            "brokk.last_asteroid", "brokk.refined", "brokk.materials",
            "brokk.ship_capabilities", "brokk.searching",
            "brokk.searching_sale", "brokk.no_target", "brokk.no_location",
            "brokk.journal_confirmed", "brokk.commander_selected",
            "guardian.unlock", "guardian.search", "guardian.reading",
            "guardian.requirements", "guardian.waiting", "guardian.where",
            "guardian.select_search", "guardian.copy_collection",
            "guardian.broker", "guardian.no_search", "guardian.copy_broker",
            "guardian.ready", "guardian.missing_units", "guardian.complete",
            "guardian.missing", "guardian.material", "guardian.run_search",
            "guardian.unavailable", "guardian.no_pending", "guardian.no_broker",
            "settings.title", "settings.heading", "settings.general_tab",
            "settings.credentials_tab", "settings.docking",
            "settings.docking_enable", "settings.docking_help",
            "settings.network", "settings.eddn", "settings.edsm", "settings.inara",
            "settings.network_restart", "settings.credentials",
            "settings.commander", "settings.frontier_id", "settings.configured",
            "settings.not_configured", "settings.secret_help",
            "settings.ai_provider", "settings.openai_model",
            "settings.ai_share_trade_data", "settings.ai_share_mining_data",
            "settings.ai_share_navigation_data", "settings.voice",
            "settings.ai_share_science_data", "settings.ai_share_progression_data",
            "settings.ai_share_powerplay_data",
            "settings.ai_share_commander_data",
            "settings.ai_share_station_search_data",
            "settings.activation", "settings.ptt", "settings.wake",
            "settings.both", "settings.calibrate", "settings.delete_profile",
            "settings.no_commander", "settings.profile_count",
            "settings.no_profile", "common.cancel", "common.accept",
            "calibration.title", "calibration.heading",
            "calibration.consent_title", "calibration.consent",
            "calibration.delete", "calibration.ready", "calibration.say",
            "calibration.order_progress", "calibration.finished",
            "calibration.saved", "calibration.speak", "calibration.record",
            "calibration.retry", "calibration.listening", "calibration.capture",
            "calibration.failed", "calibration.heard",
            "calibration.accept_sample", "common.close",
            "calibration.command.trade", "calibration.command.home",
            "calibration.command.dock", "calibration.command.night",
            "calibration.command.scoop", "calibration.command.gear",
            "calibration.command.jump", "calibration.no_commander",
            "voice.ack.1", "voice.ack.2", "voice.ack.3", "voice.ack.4",
            "voice.ack.5", "voice.listen", "voice.processing.science",
            "voice.processing.commander", "voice.processing.database",
            "voice.processing.default", "voice.unclear_retry",
            "voice.unclear_close", "freyja.voice.menu",
            "freyja.voice.unknown", "freyja.voice.quick",
            "freyja.voice.three", "freyja.voice.expedition",
            "freyja.voice.powerplay", "freyja.voice.selected",
            "mimir.descent_not_recommended", "mimir.no_evidence",
            "mimir.incomplete", "mimir.no_primary", "mimir.value",
            "mimir.value_range", "mimir.recommend", "mimir.first_logged",
            "mimir.descent_recommended", "mimir.priority_alert",
            "brokk.voice.search_start", "brokk.voice.search_failed",
            "brokk.voice.sale_search", "heimdall.voice.no_context",
            "heimdall.voice.calculating", "heimdall.voice.route_error",
            "heimdall.voice.no_base",
            "heimdall.voice.route_summary", "heimdall.voice.route_saved",
            "heimdall.voice.route_not_better", "heimdall.voice.copied",
            "heimdall.voice.arrived", "heimdall.voice.activation_error",
            "brokk.voice.unavailable", "brokk.voice.no_cargo",
            "brokk.voice.sale_result", "brokk.voice.no_sale",
            "brokk.voice.sale_busy", "brokk.voice.no_valuation",
            "brokk.voice.no_operation", "brokk.voice.target",
            "brokk.voice.summary",
            "fsd.grade.basic", "fsd.grade.standard", "fsd.grade.premium",
            "fsd.summary", "fsd.no_range", "fsd.reachable",
            "fsd.beyond_premium", "fsd.missing", "fsd.authorization_request",
            "fsd.route_mismatch", "fsd.route_clear", "fsd.detail_impossible",
            "fsd.detail_required", "fsd.detail_missing", "fsd.route_summary",
            "fsd.segment.one", "fsd.segment.many", "fsd.no_pending",
            "fsd.expired", "fsd.route_detail", "fsd.authorized",
            "dashboard.commander", "dashboard.no_system", "dashboard.biology",
            "dashboard.mining.idle", "dashboard.mining.ready",
            "dashboard.mining.prospecting", "dashboard.mining.extracting",
            "dashboard.mining.selling", "dashboard.mining.full",
            "dashboard.unclassified", "dashboard.sale_prompt",
            "dashboard.no_mining_cargo", "dashboard.consulting",
            "dashboard.no_search",
            "mimir.signals", "mimir.unknown_body", "mimir.confirmed_by",
            "mimir.reward_first", "mimir.reward_normal", "mimir.unidentified",
            "mimir.biology", "mimir.completed", "mimir.ready_next",
            "mimir.remaining",
            "dialog.route_destination", "dialog.trade_busy",
            "dialog.trade_product", "dialog.mining_target",
            "dialog.mining_busy", "dialog.commander_required",
            "dialog.save_failed", "dialog.saved",
            "console.sample", "console.species", "console.sample_complete",
            "console.next_sample", "console.ready", "console.too_close",
            "console.sample_distance", "console.route_progress",
            "console.balance", "console.activity", "console.cartography",
            "console.exobiology_base", "console.exobiology_potential",
            "console.total_base", "console.total_potential",
            "console.confirmed_paid", "console.discovery_status",
            "console.biology_detected", "console.planet",
            "console.pending_dss", "console.unknown", "console.dss_genera",
            "console.probable_species", "console.species_first",
            "brokk.voice.community_sale_error",
            "brokk.voice.sale_internal_error",
            "brokk.voice.operation_started", "brokk.voice.mineral_suffix",
            "brokk.voice.cargo_threshold", "brokk.voice.operation_finished",
            "brokk.voice.recommended_station", "brokk.voice.indicated_system",
            "brokk.status.ready", "brokk.status.prospecting",
            "brokk.status.extracting", "brokk.status.selling",
            "brokk.status.paused", "brokk.status.completed",
            "heimdall.log.calculating_route", "heimdall.log.unknown_origin",
            "heimdall.voice.replan_error", "heimdall.voice.replanned",
            "heimdall.voice.replanned_copied",
            "heimdall.voice.replan_activation_error",
            "freyja.voice.cancel_confirmed", "freyja.voice.cancel_not_confirmed",
            "freyja.voice.no_route_recalculate", "freyja.voice.cancel_instruction",
            "freyja.voice.cancelled", "freyja.voice.no_route_cancel",
            "odin.memory.confirmed", "odin.memory.no_previous",
            "odin.memory.forgotten", "odin.memory.not_found",
            "odin.memory.correction_saved", "odin.memory.correction_unsafe",
            "odin.eddn.capture_off", "odin.eddn.upload_off",
            "odin.eddn.last_sent", "odin.eddn.none_sent", "odin.eddn.active",
            "freyja.voice.ledger", "freyja.voice.consulting_bubble",
            "freyja.voice.calculation_error", "freyja.voice.busy",
            "freyja.voice.powerplay_search", "freyja.voice.no_ship_position",
            "freyja.voice.no_power", "freyja.voice.no_coordinates",
            "freyja.voice.no_powerplay_market", "freyja.voice.powerplay_result",
            "freyja.voice.community_error", "freyja.voice.no_navigation",
            "freyja.voice.release_cargo", "freyja.voice.no_power_profile",
            "freyja.voice.no_cached_operation", "freyja.voice.no_filtered_market",
            "freyja.voice.stale_cache", "freyja.voice.no_cargo_capacity",
            "freyja.voice.no_capital", "freyja.voice.no_jump_range",
            "freyja.voice.quick_summary", "freyja.voice.stale_price",
            "mimir.footfall.1", "mimir.footfall.2", "mimir.footfall.3",
            "mimir.footfall.4", "mimir.footfall.5", "mimir.this_species",
            "mimir.sample.progress.1", "mimir.sample.progress.2",
            "mimir.sample.collected", "mimir.sample.remaining.one",
            "mimir.sample.remaining.many", "mimir.sample.planet_complete",
            "mimir.sample.complete", "mimir.star_only",
            "freyja.plan.sale", "freyja.plan.bulk_discount",
            "freyja.plan.no_bulk_discount", "freyja.plan.three_summary",
            "freyja.plan.expedition_summary", "freyja.plan.stale_markets",
            "freyja.plan.powerplay_summary",
            "cockpit.docking_panel", "cockpit.feature.lights",
            "cockpit.feature.night_vision", "cockpit.unknown_state",
            "cockpit.lights.on", "cockpit.lights.off",
            "cockpit.lights.already_on", "cockpit.lights.already_off",
            "cockpit.night.on", "cockpit.night.off",
            "cockpit.night.already_on", "cockpit.night.already_off",
            "cockpit.not_main_ship", "cockpit.no_binding",
            "cockpit.turn_on", "cockpit.turn_off", "cockpit.informative",
            "cockpit.binding_join", "docking.disabled",
            "docking.not_main_ship", "docking.already_docked",
            "docking.landed", "docking.supercruise", "docking.panel_open",
            "docking.bindings_missing", "docking.send_failed", "docking.sent",
            "cockpit.vehicle_unknown", "cockpit.not_srv", "cockpit.not_ship",
            "cockpit.panel_open", "cockpit.night_activated",
            "cockpit.night_deactivated", "cockpit.scoop_deployed",
            "cockpit.scoop_retracted", "cockpit.gear_deployed",
            "cockpit.gear_retracted", "cockpit.srv_lights_on",
            "cockpit.srv_lights_off", "cockpit.srv_night_on",
            "cockpit.srv_night_off", "cockpit.srv_scoop_deployed",
            "cockpit.srv_scoop_retracted", "cockpit.hyperspace_landed",
            "cockpit.hyperspace_started", "cockpit.hyperspace_failed",
            "cockpit.unknown_control", "cockpit.binding_missing",
            "cockpit.control_failed",
            "freyja.route.powerplay_purchase", "freyja.route.purchase",
            "freyja.route.partial_sale", "freyja.route.completed",
            "freyja.route.next_leg", "freyja.route.arrived_buy",
            "freyja.route.arrived_sell", "freyja.route.docked_buy",
            "freyja.route.docked_sell", "freyja.route.none",
            "freyja.route.action_buy", "freyja.route.action_sell",
            "freyja.route.status", "freyja.route.cancel_warning",
            "freyja.route.recalc_blocker",
            "mimir.unknown_system", "mimir.unknown_body_name",
            "common.and_join", "mimir.sample.ready.1",
            "mimir.sample.ready.2", "cockpit.docking_unknown",
            "cockpit.docking_not_ship", "cockpit.docking_already",
            "cockpit.docking_surface", "cockpit.docking_supercruise",
            "cockpit.docking_no_binding", "cockpit.docking_informative",
            "voice.current_system",
        )
        for language in SUPPORTED_LANGUAGES:
            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertNotEqual(text(key, language), key)

    def test_installer_language_configuration_persists_and_assigns_voices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Config.__new__(Config)
            config.data = {}
            config.data_root = Path(directory)
            config.preferences_file = config.data_root / "preferences.json"
            config._preferences_lock = threading.Lock()

            selected = configure_language(config, "pt-BR")

            voices = VoiceSettingsRepository(config.data_root).load()
            self.assertEqual(selected, "pt-BR")
            self.assertEqual(config.language, "pt-BR")
            self.assertEqual(voices.officers["ODIN"].voice, "pt-BR-AntonioNeural")
            self.assertEqual(
                voices.officers["FREYJA"].voice, "pt-BR-FranciscaNeural"
            )

    def test_header_identifies_current_release(self) -> None:
        self.assertEqual(VERSION, "0.8.0-beta")
        self.assertEqual(
            CAPABILITY,
            "MÍMIR, HEIMDALL, FREYJA y BROKK beta",
        )


if __name__ == "__main__":
    unittest.main()
