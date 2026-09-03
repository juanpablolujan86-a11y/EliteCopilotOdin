"""
ODIN - Orbital Data Intelligence Nexus

command_center.py

Inicializa, conecta y coordina los componentes principales de ODIN.
"""

import time
import json
import logging
import threading
import queue
import re
import math
import os
from dataclasses import replace
from contextlib import redirect_stdout
from io import StringIO

from brain.decision_engine import DecisionEngine
from brokk.processor import MiningProcessor
from brokk.valuation import (
    MiningValuationError, SpanshMiningValuationClient,
    destination_risk, select_distance_tiers, select_permanent_options,
    select_recommended_destination,
)
from brokk.session import MiningSessionStore
from brokk.performance import calculate_mining_performance
from brokk.search import (
    MiningSearchError, SpanshMiningSearchClient, normalize_mineral_query,
    select_mining_distance_tiers,
)
from core.config import Config
from core.body_names import planet_reference
from core.database import DatabaseManager
from core.event_bus import EventBus
from core.expedition_ledger import ExpeditionLedger
from core.internal_events import InternalEvent
from core.journal_reader import JournalReader
from core.journal_watcher import JournalWatcher
from core.localization import text as localized_text
from core.status_watcher import StatusWatcher
from core.processors.commander_state_updater import CommanderStateUpdater
from core.processors.edsm_lookup import EDSMLookup
from core.processors.exploration_context_builder import (
    ExplorationContextBuilder,
)
from core.processors.exploration_processor import ExplorationProcessor
from mimir.event_subscriber import MimirEventSubscriber
from mimir.officer_handler import MimirOfficerHandler
from mimir.scientific_officer import ScientificOfficer
from mimir.surface_navigation import SurfaceNavigationTracker
from mimir.context_registry import ScientificContextRegistry
from models.events.voice_message_ready import VoiceMessageReady
from core.processors.jump_advisor import JumpAdvisor
from core.processors.jump_processor import JumpProcessor
from core.processors.jump_store import JumpStore
from core.processors.system_memory import SystemMemory
from services.edsm_service import EDSMService
from services.eddn_pipeline import EDDNJournalPipeline
from services.eddn_transport import EDDNDeliveryService
from services.eddn_outbox import EDDNOutboxSummary
from services.edsm_pipeline import EDSMJournalPipeline
from services.edsm_outbox import EDSMOutbox
from services.edsm_delivery import EDSMDeliveryService
from services.edsm_discard import EDSMDiscardRegistry
from services.inara_delivery import InaraDeliveryService
from services.inara_outbox import InaraOutbox
from services.inara_pipeline import InaraJournalPipeline
from services.canonn_poi import CanonnPOICatalog, CanonnPOIError
from state.commander_state import CommanderState
from ui.console_presenter import ConsolePresenter
from core.version import CAPABILITY, VERSION
from core.diagnostics import FreyjaDiagnostics, HeimdallDiagnostics, MimirDiagnostics, OdinDiagnostics
from freyja.ledger import TradeLedger, TradeSummary
from freyja.route_tracker import ActiveTradeRoute
from freyja.planner import (
    PowerplayTradeOptimizer,
    QuickRouteOptimizer,
    ThreeStationOptimizer,
    TradeExpeditionOptimizer,
    TradeProfileBuilder,
)
from freyja.market_source import MarketCache, MarketSourceError, SpanshMarketClient
from freyja.station_finder import StationFinder
from freyja.powerplay_sale import PowerplaySaleFinder
from heimdall.bindings import BindingAudit, BindingCustodian
from heimdall.cockpit import CockpitAdvisor, parse_cockpit_intent
from heimdall.docking_assist import DockingAssist
from heimdall.home_base import HomeBaseManager
from platform_adapters.clipboard import copy_text
from heimdall.navigation import NavigationContext, NavigationContextManager
from heimdall.spansh import (
    ExactRoutePlan, HeimdallRoutePlanner, SpanshClient, SpanshRouteError,
)
from heimdall.synthesis import FSDInjectionInventory
from guardian.unlocks import GuardianUnlockTracker
from guardian.search import GuardianPlanStore, GuardianSearchClient, GuardianSearchError
from engineering.planner import EngineeringTracker, normalize_engineering_objective
from intelligence.context import build_live_context
from intelligence.coordinator import IntelligenceCoordinator
from intelligence.assistant import OdinLocalAssistant
from intelligence.officer_broker import OfficerKnowledgeBroker
from intelligence.command_memory import LearnedCommand, VoiceCommandMemory
from intelligence.voice_calibration import VoiceCalibrationManager
from intelligence.reflexes import ReflexResolver, is_trade_menu_request
from intelligence.ollama import OllamaError
from intelligence.openai_client import OpenAIError
from speech.conversation import VoiceConversation
from platform_adapters.hotkey import VK_F7, create_hotkey
from speech.wake_word import WakeWordListener
from speech.recorder import MicrophoneError
from speech.whisper import TranscriptionError
from voice.service import OfficerVoiceService, VoiceServiceError
from powerplay.advisor import (
    ACTIVITIES, SpanshPowerplaySearchClient, PowerplaySearchError,
    activity_snapshot, build_powerplay_mining_plan, match_station_locations,
)
from powerplay.assignments import SOLUTION_STEPS, WeeklyAssignmentStore

class CommandCenter:
    """
    Centro de mando principal de ODIN.

    Responsabilidades:
    - Inicializar componentes.
    - Configurar procesadores.
    - Registrar suscripciones.
    - Observar el Journal.
    - Cerrar recursos correctamente.
    """

    WAKE_ACKNOWLEDGEMENTS = (
        "Sí, comandante?",
        "Lo escucho, comandante.",
        "Adelante, comandante.",
        "Dígame, comandante.",
        "A sus órdenes, comandante.",
    )
    WAKE_ACKNOWLEDGEMENT_KEYS = tuple(f"voice.ack.{index}" for index in range(1, 6))
    POWERPLAY_TRADE_CENTERS = {
        "li yong-rui": (-43.25, -64.34375, -77.6875),
    }
    BUBBLE_TRADE_CENTER = (-43.25, -64.34375, -77.6875)
    FREYJA_MARKET_MAX_AGE_HOURS = 168.0
    FREYJA_CACHE_FALLBACK_MAX_AGE_HOURS = 720.0
    FREYJA_POWERPLAY_MAX_AGE_HOURS = 24.0

    def __init__(self) -> None:
        self.config = Config()

        self.database = DatabaseManager(
            self.config.data_root
        )

        self.event_bus = EventBus()
        self.edsm_service = EDSMService()
        self.canonn_poi_catalog = CanonnPOICatalog(self.config.data_root)
        self.decision_engine = DecisionEngine()

        self.commander_state = CommanderState()
        self.console_presenter = ConsolePresenter(self.config.language)

        self.watcher: JournalWatcher | None = None
        self.eddn_pipeline: EDDNJournalPipeline | None = None
        self.eddn_delivery_service: EDDNDeliveryService | None = None
        self.edsm_pipeline: EDSMJournalPipeline | None = None
        self.edsm_delivery_service: EDSMDeliveryService | None = None
        self.inara_pipeline: InaraJournalPipeline | None = None
        self.inara_delivery_service: InaraDeliveryService | None = None
        self.status_watcher = StatusWatcher(self.config.status_file)
        self.surface_navigation = SurfaceNavigationTracker()
        self.binding_custodian = BindingCustodian(
            self.config.bindings_path,
            self.config.data_root,
        )
        self.binding_audit: BindingAudit | None = None
        self.cockpit_advisor = CockpitAdvisor(language=self.config.language)
        self.docking_assist = DockingAssist(language=self.config.language)
        self.fsd_injections = FSDInjectionInventory(
            self.config.data_root / "heimdall" / "fsd_materials.json",
            language=self.config.language,
        )
        self.guardian_unlocks = GuardianUnlockTracker()
        self.engineering = EngineeringTracker(
            self.config.data_root / "engineering" / "selected_plan.json"
        )
        self.ai_coordinator = IntelligenceCoordinator(
            OdinLocalAssistant(config=self.config),
            self.config.data_root / "intelligence" / "last_plan.json",
        )
        self.officer_broker = OfficerKnowledgeBroker()
        self.reflex_resolver = ReflexResolver()
        self._ai_plan_busy = threading.Event()
        self._ai_plan_error = ""
        self._ai_answer_busy = threading.Event()
        self._ai_answer_state: dict = {
            "question": "", "answer": "", "error": "", "model": "",
        }
        self._ai_plan_results: queue.Queue[tuple[object | None, str, bool]] = queue.Queue()
        self._officer_ai_results: queue.Queue[tuple[str, str, dict]] = queue.Queue()
        self.guardian_search = GuardianSearchClient()
        self.guardian_plan_store = GuardianPlanStore(
            self.config.data_root / "guardian" / "last_plan.json"
        )
        self._guardian_search_busy = threading.Event()
        self._guardian_plan: dict = self.guardian_plan_store.load()
        self.navigation_manager: NavigationContextManager | None = None
        self.heimdall_diagnostics = HeimdallDiagnostics(self.config.data_root)
        self.home_base_manager = HomeBaseManager(self.config.data_root)
        self.heimdall_route_planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(),
        )
        self.exploration_processor: ExplorationProcessor | None = None
        self.expedition_ledger: ExpeditionLedger | None = None
        self.brokk_processor: MiningProcessor | None = None
        self._mining_valuation_busy = threading.Event()
        self._mining_valuation_client = SpanshMiningValuationClient()
        self._mining_search_client = SpanshMiningSearchClient()
        self._mining_search_busy = threading.Event()
        self._mining_search_result: dict = {}
        self._mining_sale_manifest: dict = {}
        self.trade_profile = None
        self.market_cache: MarketCache | None = None
        self._pending_freyja_trade_menu = False
        self._pending_freyja_cancel_confirmation = False
        self._manual_trade_requests: queue.Queue[tuple[str, str, bool]] = queue.Queue()
        self._trade_calculation_busy = threading.Event()
        self._trade_requested_strategy = ""
        self._trade_requested_commodity = ""
        self._freyja_market_refresh_count = 0
        self._powerplay_sale_result: dict = {}
        self._powerplay_activity: dict = {}
        self._powerplay_search_client = SpanshPowerplaySearchClient()
        self._powerplay_market_client = SpanshMarketClient()
        self._freyja_station_finder = StationFinder(self._powerplay_market_client)
        self.powerplay_assignment_store = WeeklyAssignmentStore(self.config.data_root)
        self.voice_hotkey = create_hotkey()
        self.docking_hotkey = create_hotkey(VK_F7)
        self._voice_busy = threading.Event()
        self._voice_questions: queue.Queue[str] = queue.Queue()
        self._wake_activations: queue.Queue[bool] = queue.Queue()
        self._unclear_voice_commands: queue.Queue[bool] = queue.Queue()
        self._voice_retry_pending = False
        self._pending_engineer_confirmation: tuple[str, str] | None = None
        self._wake_acknowledgement_index = 0
        self._wake_acknowledgement_lock = threading.Lock()
        self._route_acknowledgement_done = threading.Event()
        self._route_acknowledgement_done.set()
        self._route_results: queue.Queue[tuple[object | None, str | None]] = queue.Queue()
        self._manual_route_requests: queue.Queue[str] = queue.Queue()
        self._route_calculation_busy = threading.Event()
        self._manual_exact_route_requests: queue.Queue[tuple[str, int]] = queue.Queue()
        self._exact_route_results: queue.Queue[
            tuple[ExactRoutePlan | None, str | None]
        ] = queue.Queue()
        self._exact_route_calculation_busy = threading.Event()
        self._automatic_route_results: queue.Queue[
            tuple[object | None, str | None, str]
        ] = queue.Queue()
        self._route_replan_busy = threading.Event()
        self._officer_voice_messages: queue.Queue[VoiceMessageReady] = queue.Queue()
        self._surface_ready_announced: set[tuple[int, int]] = set()
        self._heimdall_cone_announcements: set[tuple[str, str, int]] = set()
        self._mimir_visible_body_ids: set[int] = set()
        self.scientific_context = ScientificContextRegistry(self.config.language)
        self.command_memory = VoiceCommandMemory(self.database)
        self._last_voice_question = ""
        self._last_learned_command: LearnedCommand | None = None
        self._restoring_context = False
        self._stop_requested = threading.Event()
        self.dashboard_snapshot: dict = {"status": "Inicializando"}
        self._last_dashboard_refresh = 0.0
        self._last_journal_check = 0.0
        self.wake_listener = WakeWordListener(
            self.config.data_root,
            self._voice_questions.put,
            lambda: self._wake_activations.put(True),
            lambda: self._unclear_voice_commands.put(True),
        )

    def _t(self, key: str, **values) -> str:
        language = getattr(getattr(self, "config", None), "language", "es-419")
        return localized_text(key, language, **values)

    def _ai_allowed_officers(self) -> set[str] | None:
        """None significa procesamiento local; el remoto usa permisos explícitos."""

        if self.config.ai_provider == "ollama":
            return None
        allowed = set()
        if self.config.ai_share_commander_data:
            allowed.add("ODIN")
        if self.config.ai_share_science_data:
            allowed.add("MÍMIR")
        if self.config.ai_share_navigation_data:
            allowed.add("HEIMDALL")
        if self.config.ai_share_trade_data:
            allowed.add("FREYJA")
        if self.config.ai_share_mining_data:
            allowed.add("BROKK")
        if self.config.ai_share_progression_data:
            allowed.update(("INGENIERÍA", "GUARDIAN"))
        if self.config.ai_share_powerplay_data:
            allowed.add("POWERPLAY")
        return allowed

    def start(self) -> None:
        """
        Inicia ODIN y comienza a observar Elite Dangerous.
        """

        self._show_header()

        journal = self._find_active_journal()

        if journal is None:
            print("\nNo se encontró ningún Journal.")
            return

        self.database.connect()
        self.database.create_tables()

        if self.config.eddn_capture_enabled:
            self.eddn_pipeline = EDDNJournalPipeline.create(
                self.config.data_root, self.database, VERSION,
                test_mode=self.config.eddn_test_mode,
            )
            self.eddn_pipeline.bootstrap_journal(journal)
            if self.config.eddn_upload_enabled:
                self.eddn_delivery_service = EDDNDeliveryService(
                    self.config.data_root
                )
                self.eddn_delivery_service.start()
        print(self._eddn_startup_status(
            self.config.eddn_capture_enabled,
            self.config.eddn_upload_enabled,
            self.config.eddn_test_mode,
        ))
        edsm_discard_registry = None
        if self.config.edsm_capture_enabled or self.config.edsm_upload_enabled:
            edsm_discard_registry = EDSMDiscardRegistry(self.config.data_root)
        if self.config.edsm_capture_enabled:
            self.edsm_pipeline = EDSMJournalPipeline(
                EDSMOutbox(self.database), edsm_discard_registry
            )
            self.edsm_pipeline.bootstrap_journal(journal)
        if self.config.edsm_upload_enabled:
            self.edsm_delivery_service = EDSMDeliveryService(
                self.config.data_root,
                discard_registry=edsm_discard_registry,
            )
            self.edsm_delivery_service.start()
        if self.config.inara_capture_enabled:
            self.inara_pipeline = InaraJournalPipeline(InaraOutbox(self.database))
            self.inara_pipeline.bootstrap_journal(journal)
        if self.config.inara_upload_enabled:
            self.inara_delivery_service = InaraDeliveryService(self.config.data_root)
            self.inara_delivery_service.start()

        self._initialize_heimdall()

        self._initialize_heimdall_navigation(journal)

        self._initialize_fsd_materials()
        self._initialize_guardian_inventory()
        self._initialize_engineering()

        self._initialize_home_base()

        self._restore_commander_state(journal)
        self._initialize_freyja_profile()

        self._configure_processors()

        self._rebuild_current_system(journal)

        self.watcher = JournalWatcher(journal)
        self.watcher.start()

        print(f"\nJournal: {journal.name}")
        print("\nODIN está observando Elite Dangerous...")
        print("Esperando eventos.\n")
        if self.config.push_to_talk_enabled:
            print("Conversación          : presioná F8 para hablar con ODIN\n")
        if self.config.wake_word_enabled:
            print("Activación por voz     : decí ODIN y formulá tu consulta\n")
        self.wake_listener.enable_passive_listening(self.config.wake_word_enabled)
        threading.Thread(
            target=self._prepare_wake_acknowledgement,
            name="odin-prepare-wake-acknowledgement",
            daemon=True,
        ).start()
        threading.Thread(
            target=self.wake_listener.run,
            name="odin-wake-word",
            daemon=True,
        ).start()

        try:
            self._run_event_loop()

        except KeyboardInterrupt:
            print("\nODIN detenido por el comandante.")

        finally:
            self.wake_listener.stop()
            if self.eddn_delivery_service is not None:
                self.eddn_delivery_service.stop()
            if self.edsm_delivery_service is not None:
                self.edsm_delivery_service.stop()
            if self.inara_delivery_service is not None:
                self.inara_delivery_service.stop()
            self.database.disconnect()
            print("Base de datos desconectada correctamente.")

    def _initialize_heimdall(self) -> None:
        """Audita y respalda bindings sin modificar los originales."""

        self.binding_audit = self.binding_custodian.audit(create_snapshot=True)
        self.cockpit_advisor.audit = self.binding_audit
        self.docking_assist.configure(
            enabled=self.config.heimdall_auto_docking_enabled,
            audit=self.binding_audit,
        )
        self.heimdall_diagnostics.record_binding_audit(
            self.binding_audit
        )
        configured_actions = sum(
            1
            for profile in self.binding_audit.profiles
            for action in profile.actions.values()
            if action.configured
        )
        print(
            "HEIMDALL bindings    : "
            f"{len(self.binding_audit.profiles)} perfiles, "
            f"{configured_actions} acciones relevantes configuradas"
        )
        if self.binding_audit.loading_errors:
            print(
                "HEIMDALL advertencia : "
                f"{len(self.binding_audit.loading_errors)} mensajes en "
                "BindingLoadingErrors.log"
            )

    def _find_active_journal(self):
        """
        Busca el Journal más recientemente modificado.
        """

        reader = JournalReader(
            self.config.journal_path
        )

        return reader.latest_file()

    def _initialize_heimdall_navigation(self, journal) -> None:
        """Reconstruye nave, combustible, destino y ruta actuales."""

        self.navigation_manager = NavigationContextManager(
            self.database,
            self.config.navroute_file,
        )
        context = self.navigation_manager.restore(journal)
        self.heimdall_diagnostics.record_navigation_context(
            context,
            reason="inicio",
        )
        ship = context.ship_name or context.ship_type or "nave desconocida"
        destination = context.target_system or "sin destino fijado"
        fuel = (
            f"{context.fuel_main:.1f}/{context.fuel_capacity:.1f} t"
            if context.fuel_capacity > 0 else "sin datos"
        )
        print(
            "HEIMDALL navegación  : "
            f"{ship}, combustible {fuel}, destino {destination}"
        )
        progress = context.route_progress()
        if progress.remaining_jumps is not None:
            distance = (
                f", {progress.remaining_distance_ly:.1f} ly"
                if progress.remaining_distance_ly is not None else ""
            )
            print(
                "HEIMDALL ruta        : "
                f"{progress.remaining_jumps} saltos restantes{distance}"
            )
        elif progress.off_route:
            print("HEIMDALL ruta        : sistema actual fuera de la ruta cargada")

    def _restore_commander_state(self, journal) -> None:
        """Recupera el sistema actual antes de observar eventos nuevos."""

        reader = JournalReader(self.config.journal_path)
        context = reader.current_system_context(journal)
        if context is None:
            return

        updater = CommanderStateUpdater(self.commander_state)
        for event in reader.commander_context(journal):
            updater.handle_profile_event(event)
        updater.restore_context(context)
        print(
            "Estado restaurado     : "
            f"Sistema actual {self.commander_state.current_system}"
        )

    def _initialize_home_base(self) -> None:
        base = self.home_base_manager.load()
        event = JournalReader(self.config.journal_path).latest_stored_ships_event()
        if event is not None:
            base = self.home_base_manager.update_from_stored_ships(event)
        if base is None:
            print("HEIMDALL base         : sin base registrada")
            return
        location = f" ({base.station})" if base.station else ""
        print(
            f"HEIMDALL base         : {base.system}{location}, "
            f"{base.stored_ships} naves guardadas"
        )

    def _initialize_fsd_materials(self) -> None:
        event = JournalReader(self.config.journal_path).latest_materials_event()
        if event is not None:
            self.fsd_injections.handle(event)
        available = self.fsd_injections.availability()
        print(
            "HEIMDALL síntesis     : "
            f"{available.basic} básicas, {available.standard} estándar, "
            f"{available.premium} premium"
        )

    def _initialize_guardian_inventory(self) -> None:
        event = JournalReader(self.config.journal_path).latest_materials_event()
        if event is not None:
            self.guardian_unlocks.handle(event)
        if self.config.cargo_file.exists():
            try:
                self.guardian_unlocks.handle(json.loads(
                    self.config.cargo_file.read_text(encoding="utf-8")
                ))
            except (OSError, ValueError, TypeError):
                pass

    def _initialize_engineering(self) -> None:
        reader = JournalReader(self.config.journal_path)
        for event_name in ("Materials", "EngineerProgress", "Loadout"):
            event = reader.latest_event_named(event_name)
            if event is not None:
                self.engineering.handle(event)

    def _initialize_freyja_profile(self) -> None:
        if self.navigation_manager is None:
            return
        self.trade_profile = TradeProfileBuilder.build(
            self.commander_state, self.navigation_manager.context, self.config.cargo_file
        )
        print(
            "FREYJA comercio      : "
            f"{self.trade_profile.cargo_free} t libres, "
            f"{self.trade_profile.available_capital:,} créditos disponibles"
        )

    def _configure_processors(self) -> None:
        """
        Crea y registra todos los procesadores.
        """

        jump_processor = JumpProcessor()

        jump_store = JumpStore(
            self.database
        )

        system_memory = SystemMemory(
            self.database
        )

        edsm_lookup = EDSMLookup(
            self.edsm_service,
            self.database
        )

        commander_state_updater = CommanderStateUpdater(
            self.commander_state
        )

        context_builder = ExplorationContextBuilder(
            self.database
        )

        jump_advisor = JumpAdvisor(
            context_builder,
            self.decision_engine,
            self.event_bus
        )

        exploration_processor = ExplorationProcessor(
            self.database,
            self.commander_state,
            self.event_bus,
            self.surface_navigation,
            self.config.language,
        )

        scientific_officer = ScientificOfficer(
            species_file=self.config.project_root / "knowledge" / "biology" / "species.json",
            rules_file=self.config.project_root / "knowledge" / "biology" / "prediction_rules.json",
            language=self.config.language,
        )

        mimir_handler = MimirOfficerHandler(
            scientific_officer
        )

        MimirEventSubscriber(
            self.event_bus,
            mimir_handler,
        )

        for event_name in (
            "Commander", "LoadGame", "Loadout", "Statistics",
            "SetUserShipName", "ShipyardSwap", "ShipyardBuy", "Powerplay",
            "PowerplayMerits",
        ):
            self.event_bus.subscribe(event_name, commander_state_updater.handle_profile_event)
        self.event_bus.subscribe(
            "MissionAccepted", self._handle_powerplay_assignment_event,
        )
        for event_name in (
            "MissionCompleted", "MissionFailed", "MissionAbandoned",
        ):
            self.event_bus.subscribe(
                event_name, self._handle_powerplay_assignment_event,
            )
        for event_name in ("Commander", "LoadGame"):
            self.event_bus.subscribe(event_name, self._restore_acoustic_profile)
        self.event_bus.subscribe(
            "CarrierBankTransfer",
            commander_state_updater.handle_balance_event,
        )
        latest_balance = JournalReader(
            self.config.journal_path
        ).latest_player_balance_event()
        if latest_balance:
            commander_state_updater.handle_balance_event(latest_balance)
        self.event_bus.subscribe(
            "StoredShips",
            self.home_base_manager.update_from_stored_ships,
        )

        expedition_ledger = ExpeditionLedger(
            self.database,
            self.event_bus,
            self.config.project_root / "knowledge" / "biology" / "species.json",
        )
        expedition_ledger.bootstrap()
        self.expedition_ledger = expedition_ledger
        self.exploration_processor = exploration_processor

        mimir_diagnostics = MimirDiagnostics(self.config.data_root)
        freyja_diagnostics = FreyjaDiagnostics(self.config.data_root)
        if os.environ.get("ODIN_ENABLE_BROKK", "1") != "0":
            self.brokk_processor = MiningProcessor(
                MiningSessionStore(
                    self.config.data_root / "brokk" / "active_session.json"
                )
            )
            latest_loadout = JournalReader(
                self.config.journal_path
            ).latest_loadout_event()
            if latest_loadout:
                self.brokk_processor.handle(latest_loadout)
            if self.config.cargo_file.exists():
                try:
                    self.brokk_processor.handle(json.loads(
                        self.config.cargo_file.read_text(encoding="utf-8")
                    ))
                except (OSError, ValueError, TypeError):
                    pass
            restored_session = self.brokk_processor.session
            if restored_session.refined:
                self._handle_mining_cargo_ready({
                    "system": restored_session.system,
                    "body": restored_session.body,
                    "cargo": dict(restored_session.refined),
                    "produced": dict(restored_session.produced),
                    "transferred_to_carrier": dict(
                        restored_session.transferred_to_carrier
                    ),
                })
            def handle_brokk_event(event: dict) -> None:
                previous_active = self.brokk_processor.session.active
                previous_started_at = self.brokk_processor.session.started_at
                payload = event
                if event.get("event") == "Cargo" and "Inventory" not in event:
                    try:
                        snapshot = json.loads(
                            self.config.cargo_file.read_text(encoding="utf-8")
                        )
                        if int(snapshot.get("Count", -1)) == int(
                            event.get("Count", -2)
                        ):
                            payload = snapshot
                    except (OSError, ValueError, TypeError):
                        pass
                self.brokk_processor.handle(payload)
                self._announce_brokk_transition(
                    event_name=str(event.get("event", "")),
                    previous_active=previous_active,
                    previous_started_at=previous_started_at,
                )

            for event_name in MiningProcessor.EVENTS:
                self.event_bus.subscribe(event_name, handle_brokk_event)
        freyja_ledger = TradeLedger(self.database, freyja_diagnostics)
        self.freyja_ledger = freyja_ledger
        self.active_trade_route = ActiveTradeRoute(
            self.config.data_root / "freyja" / "active_route.json",
            self.event_bus,
            diagnostics=freyja_diagnostics,
            language=self.config.language,
        )
        for event_name in TradeLedger.EVENTS:
            self.event_bus.subscribe(event_name, freyja_ledger.handle)
        self.event_bus.subscribe(
            "MarketSell", self.active_trade_route.handle_market_sell
        )
        self.event_bus.subscribe(
            "MarketBuy", self.active_trade_route.handle_market_buy
        )
        self.event_bus.subscribe(
            "FSDJump", self.active_trade_route.handle_fsd_jump
        )
        self.event_bus.subscribe(
            "Docked", self.active_trade_route.handle_docked
        )
        for event_name in (
            "Materials", "MaterialCollected", "MaterialDiscarded", "Synthesis",
            "MaterialTrade", "MissionCompleted",
        ):
            self.event_bus.subscribe(event_name, self.fsd_injections.handle)
        for event_name in GuardianUnlockTracker.EVENTS:
            self.event_bus.subscribe(event_name, self.guardian_unlocks.handle)
        for event_name in EngineeringTracker.EVENTS:
            self.event_bus.subscribe(event_name, self.engineering.handle)
        market_cache = MarketCache(self.database)
        self.market_cache = market_cache
        self.event_bus.subscribe(
            "Market", lambda _event: market_cache.ingest_market_file(self.config.market_file)
        )
        odin_diagnostics = OdinDiagnostics()

        if self.navigation_manager is not None:
            for event_name in (
                "Loadout",
                "FSDTarget",
                "FSDJump",
                "Location",
                "FuelScoop",
                "ReservoirReplenished",
                "JetConeBoost",
            ):
                self.event_bus.subscribe(
                    event_name,
                    self._handle_heimdall_navigation_event,
                )


        # Eventos de salto
        self.event_bus.subscribe(
            "FSDJump",
            jump_processor.handle
        )

        self.event_bus.subscribe(
            "FSDJump",
            jump_store.handle
        )

        self.event_bus.subscribe(
            "FSDJump",
            system_memory.handle
        )

        self.event_bus.subscribe(
            "FSDJump",
            edsm_lookup.handle
        )

        self.event_bus.subscribe(
            "FSDJump",
            commander_state_updater.handle_fsd_jump
        )

        self.event_bus.subscribe("FSDJump", self._reset_mimir_dashboard)

        self.event_bus.subscribe(
            "FSDJump",
            exploration_processor.handle_fsd_jump
        )

        self.event_bus.subscribe(
            "FSDJump",
            jump_advisor.handle
        )

        self.event_bus.subscribe(
            "FSDJump",
            expedition_ledger.handle_fsd_jump,
        )

        # Eventos de exploración
        self.event_bus.subscribe(
            "Scan",
            exploration_processor.handle_scan
        )

        self.event_bus.subscribe(
            "Scan",
            expedition_ledger.handle_scan,
        )

        self.event_bus.subscribe(
            "Disembark",
            exploration_processor.handle_disembark,
        )

        self.event_bus.subscribe(
            "FSSDiscoveryScan",
            exploration_processor.handle_fss_discovery_scan
        )

        self.event_bus.subscribe(
            "FSSAllBodiesFound",
            exploration_processor.handle_fss_all_bodies_found
        )

        self.event_bus.subscribe(
            "FSSAllBodiesFound",
            expedition_ledger.handle_fss_complete,
        )

        self.event_bus.subscribe(
            "SAAScanComplete",
            exploration_processor.handle_saa_scan_complete
        )

        self.event_bus.subscribe(
            "SAAScanComplete",
            expedition_ledger.handle_mapping,
        )

        self.event_bus.subscribe(
            "SAASignalsFound",
            self._observe_mimir_biology,
        )
        self.event_bus.subscribe(
            "SAASignalsFound",
            exploration_processor.handle_saa_signals_found
        )

        self.event_bus.subscribe(
            "FSSBodySignals",
            self._observe_mimir_biology,
        )
        self.event_bus.subscribe(
            "FSSBodySignals",
            exploration_processor.handle_saa_signals_found
        )

        self.event_bus.subscribe(
            "ScanOrganic",
            self._observe_mimir_biology,
        )
        self.event_bus.subscribe(
            "ScanOrganic",
            exploration_processor.handle_scan_organic
        )

        for event_name in ("ApproachBody", "Touchdown", "Disembark", "SupercruiseExit"):
            self.event_bus.subscribe(event_name, commander_state_updater.handle_body_context)
        for event_name in ("LeaveBody", "SupercruiseEntry"):
            self.event_bus.subscribe(event_name, commander_state_updater.handle_leave_body)

        self.event_bus.subscribe(
            "ScanOrganic",
            expedition_ledger.handle_organic,
        )

        self.event_bus.subscribe(
            "SellExplorationData",
            expedition_ledger.handle_exploration_sale,
        )
        self.event_bus.subscribe("SellExplorationData", commander_state_updater.handle_sale)

        self.event_bus.subscribe(
            "MultiSellExplorationData",
            expedition_ledger.handle_exploration_sale,
        )
        self.event_bus.subscribe("MultiSellExplorationData", commander_state_updater.handle_sale)

        self.event_bus.subscribe(
            "SellOrganicData",
            expedition_ledger.handle_organic_sale,
        )
        self.event_bus.subscribe("SellOrganicData", commander_state_updater.handle_sale)

        # Eventos internos
        self.event_bus.subscribe(
            InternalEvent.RECOMMENDATION_READY,
            odin_diagnostics.record_recommendation,
        )

        self.event_bus.subscribe(
            InternalEvent.RECOMMENDATION_READY,
            self.console_presenter.show_recommendation
        )

        self.event_bus.subscribe(
            InternalEvent.EXPLORATION_REPORT_READY,
            odin_diagnostics.record_exploration_report,
        )

        self.event_bus.subscribe(
            InternalEvent.EXPLORATION_REPORT_READY,
            self.console_presenter.show_exploration_report
        )

        self.event_bus.subscribe(
            InternalEvent.SCIENTIFIC_ANALYSIS_READY,
            mimir_diagnostics.record_scientific_report,
        )

        self.event_bus.subscribe(
            InternalEvent.SCIENTIFIC_ANALYSIS_READY,
            self.console_presenter.show_scientific_report
        )
        self.event_bus.subscribe(
            InternalEvent.SCIENTIFIC_ANALYSIS_READY,
            self._remember_scientific_report,
        )

        # Se registra para el futuro sintetizador; deliberadamente no se
        # presenta en pantalla.
        self.event_bus.subscribe(
            InternalEvent.VOICE_MESSAGE_READY,
            mimir_diagnostics.record_voice_message,
        )
        self.event_bus.subscribe(
            InternalEvent.VOICE_MESSAGE_READY,
            self._officer_voice_messages.put,
        )

        self.event_bus.subscribe(
            InternalEvent.ORGANIC_SCAN_UPDATED,
            mimir_diagnostics.record_organic_scan,
        )

        self.event_bus.subscribe(
            InternalEvent.ORGANIC_SCAN_UPDATED,
            self.console_presenter.show_organic_scan
        )

        self.event_bus.subscribe(
            InternalEvent.SURFACE_NAVIGATION_UPDATED,
            mimir_diagnostics.record_surface_navigation,
        )

        self.event_bus.subscribe(
            InternalEvent.SURFACE_NAVIGATION_UPDATED,
            self.console_presenter.show_surface_navigation,
        )

        self.event_bus.subscribe(
            InternalEvent.EXPEDITION_BALANCE_UPDATED,
            odin_diagnostics.record_expedition_balance,
        )

        self.event_bus.subscribe(
            InternalEvent.EXPEDITION_BALANCE_UPDATED,
            self.console_presenter.show_expedition_balance,
        )
        self.event_bus.subscribe(
            InternalEvent.MINING_DESTINATION_SELECTED,
            self._handle_mining_destination_selected,
        )
        self.event_bus.subscribe(
            InternalEvent.MINING_CARGO_READY,
            self._handle_mining_cargo_ready,
        )

    def _rebuild_current_system(self, journal) -> None:
        """Reconstruye el FSS actual sin repetir informes en pantalla."""

        if self.exploration_processor is None:
            return

        reader = JournalReader(self.config.journal_path)
        events = reader.current_system_events(journal)
        if not events:
            return

        handlers = {
            "FSDJump": self.exploration_processor.handle_fsd_jump,
            "Location": self.exploration_processor.handle_fsd_jump,
            "CarrierJump": self.exploration_processor.handle_fsd_jump,
            "Scan": self.exploration_processor.handle_scan,
            "FSSDiscoveryScan": (
                self.exploration_processor.handle_fss_discovery_scan
            ),
            "FSSAllBodiesFound": (
                self.exploration_processor.handle_fss_all_bodies_found
            ),
            "SAAScanComplete": (
                self.exploration_processor.handle_saa_scan_complete
            ),
            "SAASignalsFound": (
                self.exploration_processor.handle_saa_signals_found
            ),
            "FSSBodySignals": (
                self.exploration_processor.handle_saa_signals_found
            ),
        }

        original_output = self.event_bus.output_stream
        silent_output = StringIO()
        self.event_bus.output_stream = silent_output
        restored = 0
        self._restoring_context = True
        try:
            with redirect_stdout(silent_output):
                for event in events:
                    if event.get("event") in {"SAASignalsFound", "FSSBodySignals"}:
                        self._observe_mimir_biology(event)
                    handler = handlers.get(event.get("event"))
                    if handler is None:
                        continue
                    handler(event)
                    restored += 1
        finally:
            self._restoring_context = False
            self.event_bus.output_stream = original_output

        print(f"Contexto reconstruido : {restored} eventos del sistema actual")

    def _run_event_loop(self) -> None:
        """
        Mantiene a ODIN escuchando eventos nuevos.
        """

        if self.watcher is None:
            raise RuntimeError(
                "JournalWatcher no fue inicializado."
            )

        while not self._stop_requested.is_set():
            status = self.status_watcher.poll()
            if status is not None:
                cockpit_state = self.cockpit_advisor.update_status(status)
                self.docking_assist.update_status(cockpit_state)
                if self.navigation_manager is not None:
                    self.navigation_manager.update_status(status)
                navigation = self.surface_navigation.update_status(status)
                if navigation is not None:
                    self.event_bus.publish_internal(
                        InternalEvent.SURFACE_NAVIGATION_UPDATED,
                        navigation,
                    )
                    ready_key = (navigation.cycle_id, navigation.progress)
                    if (
                        navigation.ready_for_sample
                        and ready_key not in self._surface_ready_announced
                    ):
                        self._surface_ready_announced.add(ready_key)
                        self.event_bus.publish_internal(
                            InternalEvent.VOICE_MESSAGE_READY,
                            VoiceMessageReady(
                                officer="MÍMIR",
                                message=self._t(
                                    f"mimir.sample.ready.{navigation.progress}"
                                ),
                                reason=(
                                    "Distancia suficiente para la siguiente muestra"
                                ),
                            ),
                        )

            if self.navigation_manager is not None:
                self.navigation_manager.poll_route()

            if not self._route_calculation_busy.is_set():
                try:
                    requested_destination = self._manual_route_requests.get_nowait()
                except queue.Empty:
                    requested_destination = ""
                if requested_destination:
                    self._start_voice_route(requested_destination)

            if not self._exact_route_calculation_busy.is_set():
                try:
                    exact_request = self._manual_exact_route_requests.get_nowait()
                except queue.Empty:
                    exact_request = None
                if exact_request:
                    self._start_exact_route(*exact_request)

            if not self._trade_calculation_busy.is_set():
                try:
                    trade_request = self._manual_trade_requests.get_nowait()
                except queue.Empty:
                    trade_request = None
                if trade_request:
                    trade_selection, commodity, allow_planetary = trade_request
                    self._start_freyja_trade_calculation(
                        trade_selection, preferred_commodity=commodity,
                        allow_planetary=allow_planetary,
                    )

            if (
                self.config.heimdall_auto_docking_enabled
                and self.docking_hotkey.pressed()
            ):
                docking_answer = self.docking_assist.request_station_docking()
                print(f"HEIMDALL: {docking_answer}")
                if not self._voice_busy.is_set():
                    self._start_fixed_voice_response(
                        docking_answer, officer="HEIMDALL"
                    )

            if (
                self.config.push_to_talk_enabled
                and self.voice_hotkey.pressed()
                and not self._voice_busy.is_set()
            ):
                print("\nODIN escucha. Hablá y terminá con un segundo de silencio...")
                self.wake_listener.arm()

            if not self._voice_busy.is_set():
                try:
                    wake_activated = self._wake_activations.get_nowait()
                except queue.Empty:
                    wake_activated = False
                if wake_activated:
                    self._voice_retry_pending = False
                    self._start_wake_acknowledgement()

            if not self._voice_busy.is_set():
                try:
                    unclear_command = self._unclear_voice_commands.get_nowait()
                except queue.Empty:
                    unclear_command = False
                if unclear_command:
                    self._handle_unclear_voice_command()

            if not self._voice_busy.is_set():
                try:
                    question = self._voice_questions.get_nowait()
                except queue.Empty:
                    question = ""
                if question:
                    self._start_voice_response(question)

            if not self._voice_busy.is_set():
                try:
                    ai_plan, ai_error, announce = self._ai_plan_results.get_nowait()
                except queue.Empty:
                    ai_plan, ai_error, announce = None, "", False
                if ai_plan is not None:
                    print(f"ODIN IA: {ai_plan.summary}")
                    if announce:
                        self._start_fixed_voice_response(
                            self._t("ai.voice_ready", summary=ai_plan.summary)
                        )
                elif ai_error and announce:
                    self._start_fixed_voice_response(self._t("ai.voice_failed"))

            if not self._voice_busy.is_set():
                try:
                    ai_question, reporting_officer, officer_report = (
                        self._officer_ai_results.get_nowait()
                    )
                except queue.Empty:
                    ai_question, reporting_officer, officer_report = "", "", {}
                if ai_question and reporting_officer:
                    self._start_ai_officer_report_response(
                        ai_question, reporting_officer, officer_report
                    )

            try:
                route_plan, route_error = self._route_results.get_nowait()
            except queue.Empty:
                route_plan, route_error = None, None
            if route_plan is not None or route_error is not None:
                self._finish_voice_route(route_plan, route_error)

            try:
                exact_plan, exact_error = self._exact_route_results.get_nowait()
            except queue.Empty:
                exact_plan, exact_error = None, None
            if exact_plan is not None or exact_error is not None:
                self._finish_exact_route(exact_plan, exact_error)

            try:
                auto_plan, auto_error, auto_destination = (
                    self._automatic_route_results.get_nowait()
                )
            except queue.Empty:
                auto_plan, auto_error, auto_destination = None, None, ""
            if auto_plan is not None or auto_error is not None:
                self._finish_automatic_replan(
                    auto_plan, auto_error, auto_destination
                )

            if not self._voice_busy.is_set():
                try:
                    officer_message = self._officer_voice_messages.get_nowait()
                except queue.Empty:
                    officer_message = None
                if officer_message is not None:
                    self._start_officer_voice_message(officer_message)

            self._follow_latest_journal()
            events = self.watcher.poll()

            for event in events:
                if self.brokk_processor is not None:
                    self.brokk_processor.observe_unknown(event)
                docking_action = self.docking_assist.handle_journal(event)
                if docking_action:
                    print(f"HEIMDALL: {docking_action} automaticamente.")
                if self.eddn_pipeline is not None:
                    self.eddn_pipeline.capture(
                        event, market_file=self.config.market_file
                    )
                if self.edsm_pipeline is not None:
                    self.edsm_pipeline.capture(event)
                if self.inara_pipeline is not None:
                    self.inara_pipeline.capture(
                        event, cargo_file=self.config.cargo_file
                    )
                self.event_bus.publish(event)

            now = time.monotonic()
            if now - self._last_dashboard_refresh >= 0.5:
                self._refresh_dashboard_snapshot()
                self._last_dashboard_refresh = now

            time.sleep(0.1)

    def _follow_latest_journal(self) -> None:
        """Sigue automáticamente el Journal nuevo cuando Elite reinicia sesión."""

        now = time.monotonic()
        if now - self._last_journal_check < 1.0 or self.watcher is None:
            return
        self._last_journal_check = now
        latest = JournalReader(self.config.journal_path).latest_file()
        if latest is None or latest == self.watcher.journal_file:
            return
        self.watcher.follow(latest, replay_existing=True)
        print(f"Journal actualizado   : {latest.name}")

    def request_stop(self) -> None:
        """Solicita un cierre ordenado desde la interfaz gráfica."""

        self._stop_requested.set()

    def apply_voice_activation_mode(self, *, wake_enabled: bool) -> None:
        """Aplica en caliente la escucha pasiva guardada en Configuración."""

        if not wake_enabled:
            self.wake_listener.armed.clear()
        self.wake_listener.enable_passive_listening(wake_enabled)
        if wake_enabled:
            return
        for pending in (
            self._wake_activations,
            self._voice_questions,
            self._unclear_voice_commands,
        ):
            while True:
                try:
                    pending.get_nowait()
                except queue.Empty:
                    break

    def _restore_acoustic_profile(self, _event: dict) -> None:
        """Restaura sólo el perfil del comandante identificado por el Journal."""

        commander = self.commander_state.fid or self.commander_state.commander_name
        if not commander:
            return
        status = VoiceCalibrationManager(self.command_memory).status(commander)
        if not status.get("acoustic_samples"):
            return
        self.wake_listener.recorder.apply_acoustic_profile(status)
        self.wake_listener.command_silence_seconds = (
            self.wake_listener.recorder.command_silence_seconds
        )

    def _refresh_dashboard_snapshot(self) -> None:
        navigation = (
            self.navigation_manager.context
            if self.navigation_manager is not None else NavigationContext()
        )
        balance = (
            self.expedition_ledger.summary("interfaz")
            if self.expedition_ledger is not None else None
        )
        predictions = self.scientific_context.system_predictions(
            self.commander_state.current_system
        )
        prediction_values = self.scientific_context.system_prediction_values(
            self.commander_state.current_system
        )
        prediction_rewards = self.scientific_context.system_prediction_rewards(
            self.commander_state.current_system
        )
        biology = self._dashboard_biology(
            predictions, prediction_values, prediction_rewards
        )
        trade = self._dashboard_trade()
        mining = self._dashboard_mining()
        try:
            route = self.heimdall_route_planner.active_route_snapshot(navigation)
        except (RuntimeError, ValueError, TypeError):
            route = {}
        injections = self.fsd_injections.availability()
        community_status = "unknown"
        if self.commander_state.system_address:
            rows = self.database.query(
                "SELECT found FROM edsm_system_cache WHERE system_address = ?",
                (self.commander_state.system_address,),
            )
            if rows:
                community_status = "registered" if rows[0]["found"] else "unregistered"
        snapshot = {
            "status": "Operativo",
            "commander": self.commander_state.commander_name or "Comandante",
            "frontier_id": self.commander_state.fid or "",
            "credits": int(self.commander_state.credits or 0),
            "system": self.commander_state.current_system or "Sin sistema",
            "community_status": community_status,
            "body": self.commander_state.current_body or "",
            "ship": (
                navigation.ship_name or self.commander_state.ship_name
                or navigation.ship_type or "Nave desconocida"
            ),
            "ship_ident": navigation.ship_ident or self.commander_state.ship_ident,
            "fuel": float(navigation.fuel_main or 0),
            "fuel_capacity": float(navigation.fuel_capacity or 0),
            "jump_range": float(navigation.max_jump_range or 0),
            "fsd_health": navigation.fsd_health,
            "exact_plotter": navigation.exact_plotter_readiness(),
            "high_energy": {
                "charged": navigation.boost_charged,
                "boost_value": navigation.last_boost_value,
                "fsd_health": navigation.fsd_health,
                "target_class": navigation.target_star_class,
            },
            "route": route,
            "route_calculating": (
                self._route_calculation_busy.is_set()
                or not self._manual_route_requests.empty()
                or self._exact_route_calculation_busy.is_set()
                or not self._manual_exact_route_requests.empty()
            ),
            "biology": biology,
            "trade": trade,
            "mining": mining,
            "powerplay": {
                **activity_snapshot(self.commander_state, self._powerplay_activity),
            },
            "injections": {
                "basic": injections.basic,
                "standard": injections.standard,
                "premium": injections.premium,
            },
            "guardian": {
                **self.guardian_unlocks.snapshot(),
                "plan": dict(self._guardian_plan),
                "calculating": self._guardian_search_busy.is_set(),
            },
            "engineering": self.engineering.snapshot(),
            "ai": {
                **self.ai_coordinator.snapshot(),
                **self.officer_broker.snapshot(),
                "calculating": self._ai_plan_busy.is_set(),
                "error": self._ai_plan_error,
                "provider": self.config.ai_provider,
                "model": (self.config.openai_model
                          if self.config.ai_provider == "openai" else "ollama"),
                "conversation": {
                    **dict(self._ai_answer_state),
                    "calculating": self._ai_answer_busy.is_set(),
                },
                "reflexes": self._reflex_engine().snapshot(),
            },
            "network": {
                "eddn": self.eddn_delivery_service is not None,
                "edsm": self.edsm_delivery_service is not None,
                "inara": self.inara_delivery_service is not None,
            },
        }
        if balance is not None:
            snapshot["expedition"] = {
                "cartography": balance.cartography_estimated,
                "exobiology_base": balance.exobiology_base,
                "exobiology_potential": balance.exobiology_potential,
                "total_base": balance.total_base,
                "total_potential": balance.total_potential,
                "systems": balance.systems_visited,
                "bodies": balance.bodies_scanned,
                "species": balance.species_completed,
            }
        self.dashboard_snapshot = snapshot

    def _dashboard_mining(self) -> dict:
        processor = getattr(self, "brokk_processor", None)
        if processor is None:
            return {"active": False, "status": "Sin operación minera"}
        session = processor.session
        performance = calculate_mining_performance(
            session, self._mining_duration_hours(session)
        )
        cargo_capacity = int(
            getattr(getattr(self, "trade_profile", None), "cargo_capacity", 0) or 0
        )
        return {
            "active": session.active,
            "status": session.status,
            "system": session.system,
            "body": session.body,
            "technique": session.technique,
            "technique_source": session.technique_source,
            "technique_confirmed": session.technique_confirmed,
            "target": session.target_mineral,
            "prospected": session.prospected_asteroids,
            "cracked": session.cracked_asteroids,
            "last_prospect": dict(session.last_prospect),
            "refined": dict(session.refined),
            "refined_total": session.refined_total,
            "produced": dict(session.produced),
            "produced_total": performance.produced_tonnes,
            "duration_hours": performance.duration_hours,
            "performance": performance.to_dict(),
            "cargo_capacity": int(
                session.equipment.get("cargo_capacity", cargo_capacity) or 0
            ),
            "cargo_count": session.cargo_count,
            "cargo_inventory": dict(session.cargo_inventory),
            "limpets": session.limpets,
            "transferred_to_carrier": dict(session.transferred_to_carrier),
            "cargo_full": bool(
                session.equipment.get("cargo_capacity", cargo_capacity)
                and session.cargo_count >= int(
                    session.equipment.get("cargo_capacity", cargo_capacity) or 0
                )
            ),
            "materials": dict(session.engineering_materials),
            "environment": session.mining_environment,
            "surface_vehicle": session.surface_vehicle,
            "surface_vehicle_active": session.surface_vehicle_active,
            "geological_signals": session.geological_signals,
            "surface_event_count": len(session.surface_mining_events),
            "sale_revenue": session.sale_revenue,
            "equipment": dict(session.equipment),
            "valuation": dict(session.valuation),
            "valuation_calculating": self._mining_valuation_busy.is_set(),
            "sale_manifest": dict(self._mining_sale_manifest),
            "search": {
                **dict(self._mining_search_result),
                "calculating": self._mining_search_busy.is_set(),
            },
        }

    def _maybe_refresh_mining_valuation(
        self, *, force: bool = False, announce: bool = False,
    ) -> bool:
        processor = self.brokk_processor
        if processor is None or self._mining_valuation_busy.is_set():
            return False
        session = processor.session
        capacity = int(session.equipment.get("cargo_capacity", 0) or 0)
        if (
            not capacity or not session.cargo_inventory
            or (not force and session.cargo_count < capacity)
        ):
            return False
        commodity, quantity = max(
            session.cargo_inventory.items(), key=lambda item: int(item[1] or 0)
        )
        aliases = {"painita": "Painite", "platino": "Platinum"}
        query_name = aliases.get(commodity.casefold(), commodity)
        previous = session.valuation
        if (
            previous.get("commodity") == commodity
            and int(previous.get("quantity", 0) or 0) == int(quantity)
            and previous.get("best_permanent", {}).get("risk")
            and previous.get("best_global_permanent", {}).get("risk")
            and "global_permanent_options" in previous
            and "distance_options" in previous
        ):
            return False
        self._mining_valuation_busy.set()

        def worker() -> None:
            try:
                destinations = self._mining_valuation_client.destinations(
                    session.system or self.commander_state.current_system,
                    query_name,
                    int(quantity),
                )
                permanent = select_recommended_destination(destinations)
                carrier = next((item for item in destinations if item.carrier), None)
                global_destinations = self._mining_valuation_client.global_destinations(
                    query_name,
                    int(quantity),
                    tuple(self.commander_state.star_position)
                    if self.commander_state.star_position else None,
                )
                global_permanent = select_recommended_destination(global_destinations)
                global_options = select_permanent_options(
                    global_destinations, limit=3, max_distance_ly=900.0
                )
                tier_options = select_distance_tiers(
                    tuple({
                        (item.system, item.station): item
                        for item in (*destinations, *global_destinations)
                    }.values())
                )
                permanent_data = permanent.to_dict() if permanent else {}
                if permanent:
                    permanent_data["risk"] = destination_risk(permanent)
                global_data = global_permanent.to_dict() if global_permanent else {}
                if global_permanent:
                    global_data["risk"] = destination_risk(global_permanent)
                session.valuation = {
                    "commodity": commodity,
                    "quantity": int(quantity),
                    "best_permanent": permanent_data,
                    "best_carrier": carrier.to_dict() if carrier else {},
                    "best_global_permanent": global_data,
                    "global_permanent_options": [
                        {**item.to_dict(), "risk": destination_risk(item)}
                        for item in global_options
                    ],
                    "distance_options": {
                        name: {**item.to_dict(), "risk": destination_risk(item)}
                        for name, item in tier_options.items()
                    },
                }
                processor.store.save(session)
                if announce:
                    self.event_bus.publish_internal(
                        InternalEvent.VOICE_MESSAGE_READY,
                        VoiceMessageReady(
                            "BROKK", self._brokk_sale_voice_summary(),
                            "resultado de búsqueda de venta minera",
                        ),
                    )
            except MiningValuationError:
                session.valuation = {
                    "commodity": commodity, "quantity": int(quantity),
                    "error": "No fue posible actualizar precios comunitarios.",
                }
                processor.store.save(session)
                if announce:
                    self.event_bus.publish_internal(
                        InternalEvent.VOICE_MESSAGE_READY,
                        VoiceMessageReady(
                            "BROKK",
                            self._t("brokk.voice.community_sale_error"),
                            "error de búsqueda de venta minera",
                        ),
                    )
            except Exception as error:
                session.valuation = {
                    "commodity": commodity, "quantity": int(quantity),
                    "error": "Falló el cálculo de categorías de distancia.",
                    "diagnostic": f"{type(error).__name__}: {error}",
                }
                processor.store.save(session)
                if announce:
                    self.event_bus.publish_internal(
                        InternalEvent.VOICE_MESSAGE_READY,
                        VoiceMessageReady(
                            "BROKK",
                            self._t("brokk.voice.sale_internal_error"),
                            "error interno de valoración minera",
                        ),
                    )
            finally:
                self._mining_valuation_busy.clear()

        threading.Thread(target=worker, daemon=True).start()
        return True

    def request_mining_sale_search(self) -> bool:
        """Consulta precios externos sólo tras una acción explícita."""

        return self._maybe_refresh_mining_valuation(force=True)

    def _announce_brokk_transition(
        self, *, event_name: str, previous_active: bool,
        previous_started_at: str,
    ) -> None:
        """Publica hitos útiles sin leer cada evento o tonelada del Journal."""

        processor = self.brokk_processor
        if processor is None:
            return
        session = processor.session
        messages: list[tuple[str, str]] = []
        if event_name == "MiningRefined" and not previous_started_at and session.started_at:
            mineral = next(reversed(session.produced), session.target_mineral)
            messages.append((
                self._t(
                    "brokk.voice.operation_started",
                    mineral=(self._t("brokk.voice.mineral_suffix", mineral=mineral)
                             if mineral else ""),
                ),
                "inicio automático de operación minera",
            ))

        capacity = max(0, int(session.equipment.get("cargo_capacity", 0) or 0))
        if event_name == "Cargo" and capacity and session.active:
            percentage = (max(0, session.cargo_count) * 100) / capacity
            reached = [threshold for threshold in (75, 90, 100) if percentage >= threshold]
            new_levels = [
                threshold for threshold in reached
                if threshold not in session.announced_fill_levels
            ]
            if new_levels:
                session.announced_fill_levels.extend(new_levels)
                threshold = max(new_levels)
                messages.append((
                    self._t("brokk.voice.cargo_threshold", threshold=threshold),
                    f"bodega minera al {threshold} por ciento",
                ))
                processor.store.save(session)

        if previous_active and not session.active and session.status == "completed":
            performance = calculate_mining_performance(
                session, self._mining_duration_hours(session)
            )
            messages.append((
                self._t(
                    "brokk.voice.operation_finished",
                    produced=f"{performance.produced_tonnes:g}",
                    rate=f"{performance.tonnes_per_hour:g}",
                ),
                "cierre automático de operación minera",
            ))
            mined_cargo = {
                commodity: max(0, int(quantity or 0))
                for commodity, quantity in session.refined.items()
                if int(quantity or 0) > 0
            }
            if mined_cargo:
                self.event_bus.publish_internal(
                    InternalEvent.MINING_CARGO_READY,
                    {
                        "system": session.system,
                        "body": session.body,
                        "cargo": mined_cargo,
                        "produced": dict(session.produced),
                        "transferred_to_carrier": dict(
                            session.transferred_to_carrier
                        ),
                        "source": "BROKK",
                    },
                )

        for message, reason in messages:
            self.event_bus.publish_internal(
                InternalEvent.VOICE_MESSAGE_READY,
                VoiceMessageReady("BROKK", message, reason, session.body),
            )

    @staticmethod
    def _mining_duration_hours(session) -> float:
        if not session.started_at:
            return 0.0
        try:
            from datetime import datetime, timezone
            started = datetime.fromisoformat(session.started_at.replace("Z", "+00:00"))
            ended_text = session.ended_at if not session.active else ""
            ended = (
                datetime.fromisoformat(ended_text.replace("Z", "+00:00"))
                if ended_text else datetime.now(timezone.utc)
            )
            return max(0.0, (ended - started).total_seconds() / 3600.0)
        except (TypeError, ValueError):
            return 0.0

    def _dashboard_trade(self) -> dict:
        summary = (
            self.freyja_ledger.summary()
            if getattr(self, "freyja_ledger", None) is not None else None
        )
        state = getattr(getattr(self, "active_trade_route", None), "state", None)
        result = {
            "active": False,
            "strategy": "Sin modalidad activa",
            "commodity": "—", "target": "—", "units": 0,
            "estimated_profit": 0,
            "realized_profit": int(summary.realized_profit if summary else 0),
            "cargo_units": int(summary.cargo_units if summary else 0),
            "progress": "Sin ruta comercial activa",
            "calculating": (
                getattr(self, "_trade_calculation_busy", threading.Event()).is_set()
                or (
                    getattr(self, "_manual_trade_requests", None) is not None
                    and not self._manual_trade_requests.empty()
                )
            ),
            "requested_strategy": getattr(self, "_trade_requested_strategy", ""),
            "requested_commodity": getattr(self, "_trade_requested_commodity", ""),
            "unit_price": 0,
            "distance_ly": 0.0,
            "powerplay_state": "—",
        }
        # Texto ASCII deliberado para configuraciones regionales de Windows.
        result["powerplay_state"] = "Sin datos"
        powerplay_result = getattr(self, "_powerplay_sale_result", None)
        if powerplay_result:
            result.update(powerplay_result)
            return result
        if not state:
            return result
        legs = state.get("legs", [])
        index = int(state.get("index", 0) or 0)
        if not legs or index >= len(legs):
            return result
        leg = legs[index]
        phase = state.get("phase", "to_buy")
        to_buy = phase == "to_buy"
        units = int(leg.get("units", 0) or 0)
        if not to_buy:
            units = max(
                0,
                int(state.get("bought_units", units) or 0)
                - int(state.get("sold_units", 0) or 0),
            )
        strategy_names = {
            "quick": "Ruta rápida", "three_station": "Tres estaciones",
            "expedition": "Expedición comercial", "powerplay": "Powerplay",
        }
        result.update({
            "active": True,
            "strategy": strategy_names.get(state.get("strategy"), "Comercio"),
            "commodity": leg.get("commodity", "—"),
            "target": (
                f"{leg.get('buy_station', '—')} · {leg.get('buy_system', '—')}"
                if to_buy else
                f"{leg.get('sell_station', '—')} · {leg.get('sell_system', '—')}"
            ),
            "units": units,
            "estimated_profit": int(state.get("estimated_profit", 0) or 0),
            "progress": f"Tramo {index + 1} de {len(legs)} · {'COMPRA' if to_buy else 'VENTA'}",
        })
        return result

    def _reset_mimir_dashboard(self, _event: dict) -> None:
        """Vacía la vista científica al comenzar un sistema nuevo."""

        self._mimir_visible_body_ids.clear()
        self.surface_navigation.reset()
        self.dashboard_snapshot["biology"] = {
            "bodies": 0, "species": 0, "predictions": {}, "details": (),
        }

    def _observe_mimir_biology(self, event: dict) -> None:
        """Habilita un cuerpo cuando el Journal informa biología nueva."""

        body_id = event.get("BodyID", event.get("Body"))
        if body_id is None:
            return
        is_organic = event.get("event") == "ScanOrganic"
        has_biology = bool(event.get("Genuses")) or any(
            ExplorationProcessor._is_biological_signal(signal)
            for signal in event.get("Signals", ())
        )
        if is_organic or has_biology:
            self._mimir_visible_body_ids.add(int(body_id))

    def _dashboard_biology(
        self,
        predictions: dict[str, tuple[str, ...]],
        prediction_values: dict[str, dict[str, int]] | None = None,
        prediction_rewards: dict[str, dict[str, tuple[int, int]]] | None = None,
    ) -> dict:
        """Combina señales reales persistidas con predicciones de MÍMIR."""

        bodies: dict[tuple[int | None, str], dict] = {}
        if self.commander_state.system_address:
            rows = self.database.query(
                """
                SELECT body_id, body_name, source_event, signal_type,
                       signal_count, genus, species, scan_type
                FROM biological_signals
                WHERE system_address = ?
                ORDER BY body_id, id
                """,
                (self.commander_state.system_address,),
            )
            known_names = {
                row["body_id"]: row["body_name"]
                for row in self.database.query(
                    "SELECT body_id, body_name FROM stellar_bodies WHERE system_address = ?",
                    (self.commander_state.system_address,),
                )
            }
            for row in rows:
                body_id = row["body_id"]
                visible_ids = getattr(self, "_mimir_visible_body_ids", None)
                if visible_ids is not None and body_id not in visible_ids:
                    continue
                body_name = row["body_name"] or known_names.get(body_id) or f"Cuerpo {body_id}"
                key = (body_id, body_name)
                item = bodies.setdefault(key, {
                    "body": body_name, "signals": 0,
                    "confirmed": set(), "probable": set(), "sampling": {},
                    "dss_confirmed": False,
                })
                if (
                    row["source_event"] in {"FSSBodySignals", "SAASignalsFound"}
                    and row["signal_type"] == "Biological"
                ):
                    item["signals"] = max(item["signals"], int(row["signal_count"] or 0))
                for value in (row["genus"], row["species"]):
                    if value:
                        item["confirmed"].update(
                            part.strip() for part in str(value).split(",") if part.strip()
                        )
                if row["source_event"] == "SAASignalsFound" and row["genus"]:
                    item["dss_confirmed"] = True
                if row["source_event"] == "ScanOrganic":
                    sample_name = row["species"] or row["genus"] or "Biología"
                    progress = {"Log": 1, "Sample": 2, "Analyse": 3}.get(
                        row["scan_type"], 0
                    )
                    item["sampling"][sample_name] = max(
                        progress, item["sampling"].get(sample_name, 0)
                    )
        by_name = {item["body"].casefold(): item for item in bodies.values()}
        for body_name, species in predictions.items():
            body_id = next(
                (identifier for identifier, name in known_names.items()
                 if name.casefold() == body_name.casefold()),
                None,
            ) if self.commander_state.system_address else None
            visible_ids = getattr(self, "_mimir_visible_body_ids", None)
            if visible_ids is not None and body_id not in visible_ids:
                continue
            item = by_name.get(body_name.casefold())
            if item is None:
                item = {
                    "body": body_name, "signals": 0,
                    "confirmed": set(), "probable": set(), "sampling": {},
                    "dss_confirmed": False,
                }
                bodies[(None, body_name)] = item
                by_name[body_name.casefold()] = item
            if not item["dss_confirmed"] and not item["sampling"]:
                item["probable"].update(species)
        current_body = str(
            getattr(self.commander_state, "current_body", "") or ""
        ).casefold()
        if current_body:
            bodies = {
                key: item for key, item in bodies.items()
                if item["body"].casefold() == current_body
            }
        details = tuple({
            "body": item["body"],
            "signals": item["signals"],
            "confirmed": tuple(sorted(item["confirmed"])),
            "confirmation": "DSS" if item["dss_confirmed"] else (
                "MUESTRA" if item["sampling"] else ""
            ),
            "probable": tuple(sorted(item["probable"])),
            "probable_values": {
                species: int(value)
                for species, value in (prediction_values or {}).get(
                    item["body"], {}
                ).items()
                if species in item["probable"]
            },
            "probable_rewards": {
                species: {"base": int(base), "potential": int(potential)}
                for species, (base, potential) in (prediction_rewards or {}).get(
                    item["body"], {}
                ).items()
                if species in item["probable"]
            },
            "sampling": tuple({
                "species": species,
                "progress": progress,
                "distance_m": (
                    self.surface_navigation.distance_m
                    if species == self.surface_navigation.species
                    and progress in (1, 2) else None
                ),
                "required_distance_m": (
                    self.surface_navigation.required_distance_m
                    if species == self.surface_navigation.species
                    and progress in (1, 2) else None
                ),
                "ready": (
                    self.surface_navigation.ready_for_sample
                    if species == self.surface_navigation.species
                    and progress in (1, 2) else False
                ),
            } for species, progress in sorted(item["sampling"].items())),
        } for item in bodies.values() if item["signals"] or item["confirmed"] or item["probable"])
        return {
            "bodies": len(details),
            "species": sum(max(item["signals"], len(item["confirmed"]), len(item["probable"])) for item in details),
            "predictions": predictions,
            "details": details,
        }

    def _start_wake_acknowledgement(self) -> None:
        self._powerplay_sale_result["target"] = "Sin destino"
        self._voice_busy.set()
        threading.Thread(
            target=self._run_wake_acknowledgement,
            name="odin-wake-acknowledgement",
            daemon=True,
        ).start()

    def _prepare_wake_acknowledgement(self) -> None:
        try:
            warm_up = getattr(self.wake_listener.transcriber, "warm_up", None)
            if self.config.wake_word_enabled and callable(warm_up):
                ready = warm_up()
                print(
                    "Reconocimiento de voz: "
                    + ("Faster Whisper Small listo" if ready else "whisper.cpp de respaldo")
                )
            elif not self.config.wake_word_enabled:
                print("Reconocimiento de voz: carga diferida hasta presionar F8")
            voice = OfficerVoiceService(self.config)
            messages = tuple(
                ("ODIN", self._t(key)) for key in self.WAKE_ACKNOWLEDGEMENT_KEYS
            ) + (
                ("ODIN", self._t("voice.processing.database")),
                ("ODIN", self._t("voice.processing.science")),
                ("ODIN", self._t("voice.processing.commander")),
                ("ODIN", self._t("voice.processing.default")),
                ("HEIMDALL", "Calculando la ruta, comandante."),
                (
                    "FREYJA",
                    self._t("freyja.voice.quick"),
                ),
                (
                    "FREYJA",
                    self._t("freyja.voice.three"),
                ),
                (
                    "FREYJA",
                    self._t("freyja.voice.expedition"),
                ),
                (
                    "FREYJA",
                    self._t("freyja.voice.powerplay"),
                ),
            )
            for officer, message in messages:
                voice.prepare(officer, message)
        except (VoiceServiceError, OSError):
            pass

    def _run_wake_acknowledgement(self) -> None:
        try:
            acknowledgement = self._next_wake_acknowledgement()
            print(f"ODIN: {acknowledgement}\n")
            OfficerVoiceService(self.config).speak("ODIN", acknowledgement)
            print(self._t("voice.listen"))
        except VoiceServiceError as error:
            print(f"Voz de ODIN no disponible: {error}\n")
        finally:
            self._voice_busy.clear()
            self.wake_listener.resume()

    def _next_wake_acknowledgement(self) -> str:
        with self._wake_acknowledgement_lock:
            key = self.WAKE_ACKNOWLEDGEMENT_KEYS[
                self._wake_acknowledgement_index
            ]
            self._wake_acknowledgement_index = (
                self._wake_acknowledgement_index + 1
            ) % len(self.WAKE_ACKNOWLEDGEMENTS)
            return self._t(key)

    def _start_voice_response(self, question: str) -> None:
        """Responde en segundo plano sin detener el seguimiento del Journal."""
        print("\n" + self._t("voice.commander_dictation", text=question))
        if self._is_voice_listening_cancel(question):
            self._voice_retry_pending = False
            self.wake_listener.armed.clear()
            if re.search(r"\bsilencio\b", question, flags=re.IGNORECASE):
                print("ODIN: escucha cancelada.")
                self.wake_listener.resume()
                return
            self._start_fixed_voice_response(self._t("voice.listening_cancelled"))
            return
        pending_engineer = getattr(self, "_pending_engineer_confirmation", None)
        if pending_engineer is not None:
            spoken_name, candidate = pending_engineer
            self._pending_engineer_confirmation = None
            if self._is_affirmative_voice_answer(question):
                self.engineering.learn_voice_alias(spoken_name, candidate)
                if self.request_ai_plan(f"desbloquear al ingeniero {candidate}", announce=True):
                    self._start_fixed_voice_response(self._t("ai.voice_started"))
                else:
                    self._start_fixed_voice_response(self._t("ai.already_working"))
            else:
                self._start_fixed_voice_response(
                    self._t("engineering.voice_repeat_name"), arm_after=True
                )
            return
        spoken_engineer = self._engineer_unlock_spoken_name(question)
        if spoken_engineer:
            resolved = self.engineering.resolve_engineer(spoken_engineer)
            if resolved:
                if self.request_ai_plan(f"desbloquear al ingeniero {resolved}", announce=True):
                    self._start_fixed_voice_response(self._t("ai.voice_started"))
                else:
                    self._start_fixed_voice_response(self._t("ai.already_working"))
                return
            candidates = self.engineering.engineer_candidates(spoken_engineer)
            if candidates and candidates[0][1] >= 0.42:
                candidate = candidates[0][0]
                self._pending_engineer_confirmation = (spoken_engineer, candidate)
                self._start_fixed_voice_response(
                    self._t("engineering.voice_confirm", engineer=candidate),
                    arm_after=True,
                )
            else:
                self._start_fixed_voice_response(
                    self._t("engineering.voice_unknown"), arm_after=True
                )
            return
        if self._is_nearby_station_request(question):
            self._start_ai_station_search(question)
            return
        if getattr(self, "_pending_freyja_cancel_confirmation", False):
            if self._is_freyja_trade_cancel_confirmation(question):
                self._pending_freyja_cancel_confirmation = False
                self.active_trade_route.cancel()
                self._start_fixed_voice_response(
                    self._t("freyja.voice.cancel_confirmed"),
                    officer="FREYJA",
                )
            else:
                self._start_fixed_voice_response(
                    self._t("freyja.voice.cancel_not_confirmed"),
                    officer="FREYJA",
                    arm_after=True,
                )
            return
        if self._pending_freyja_trade_menu:
            selection = self._freyja_trade_selection(question)
            if selection is not None:
                self._pending_freyja_trade_menu = False
                self._start_freyja_trade_calculation(selection)
                return
            self._start_fixed_voice_response(
                self._t("freyja.voice.unknown"),
                officer="FREYJA",
                arm_after=True,
            )
            return
        standalone_selection = self._freyja_trade_selection(question)
        if standalone_selection is not None and re.search(
            r"\b(?:opci\u00f3n|opcion|modelo|modalidad)\b", question.casefold()
        ):
            self._start_freyja_trade_calculation(standalone_selection)
            return
        if not self._is_credible_voice_question(question):
            self._handle_unclear_voice_command()
            return
        self._voice_retry_pending = False
        commander = self.commander_state.fid or self.commander_state.commander_name or "default"
        lowered = question.casefold().strip()
        previous_question = self._last_voice_question

        ai_objective = self._ai_plan_objective(question)
        if ai_objective is not None:
            if self.request_ai_plan(ai_objective, announce=True):
                self._start_fixed_voice_response(self._t("ai.voice_started"))
            else:
                self._start_fixed_voice_response(self._t("ai.already_working"))
            return

        powerplay_activity = self._powerplay_activity_request(question)
        if powerplay_activity is not None:
            activity, subject = powerplay_activity
            started, message = self.request_powerplay_activity(
                activity, subject, ai_question=question
            )
            if started:
                self._start_fixed_voice_response(
                    self._t("ai.powerplay_searching"), officer="ODIN"
                )
            else:
                self._start_fixed_voice_response(message, officer="ODIN")
            return

        powerplay_sale = self._freyja_powerplay_sale_request(question)
        if powerplay_sale is not None:
            self._start_freyja_powerplay_sale_search(powerplay_sale)
            return

        if self._is_freyja_trade_request(question):
            self._reflex_engine().resolve(question)
            self.command_memory.remember(
                commander, question, "freyja_trade_menu", {}
            )
            self._open_freyja_trade_menu()
            return

        mining_target = self._brokk_mining_request(question)
        if mining_target is not None:
            if self.request_mining_search(mining_target, ai_question=question):
                self._start_fixed_voice_response(
                    self._t("ai.consulting_officer", officer="BROKK"),
                    officer="ODIN",
                )
            else:
                self._start_fixed_voice_response(
                    self._t("brokk.voice.search_failed"),
                    officer="BROKK",
                )
            return

        if self._is_brokk_sale_request(question):
            if self._maybe_refresh_mining_valuation(force=True, announce=True):
                answer = self._t("brokk.voice.sale_search")
            else:
                answer = self._brokk_sale_voice_summary()
            self._start_fixed_voice_response(answer, officer="BROKK")
            return

        if self._is_brokk_status_request(question):
            self._start_fixed_voice_response(
                self._brokk_voice_summary(), officer="BROKK"
            )
            return

        if self._is_eddn_status_request(question):
            summary = (
                self.eddn_pipeline.outbox.summary()
                if self.eddn_pipeline is not None else
                EDDNOutboxSummary(0, 0, 0, 0, "")
            )
            self._start_fixed_voice_response(
                self._eddn_voice_summary(
                    summary,
                    self.config.eddn_capture_enabled,
                    self.config.eddn_upload_enabled,
                    self.config.language,
                )
            )
            return

        if self._is_freyja_trade_status_request(question):
            self._start_fixed_voice_response(
                self.active_trade_route.status_message(), officer="FREYJA"
            )
            return

        if self._is_freyja_trade_ledger_request(question):
            self._start_fixed_voice_response(
                self._freyja_ledger_voice_summary(
                    self.freyja_ledger.summary(), self.config.language
                ),
                officer="FREYJA",
            )
            return

        if self._is_freyja_trade_recalculate_request(question):
            strategy = self.active_trade_route.active_strategy()
            if strategy is None:
                self._start_fixed_voice_response(
                    self._t("freyja.voice.no_route_recalculate"),
                    officer="FREYJA",
                )
            elif blocker := self.active_trade_route.recalculation_blocker():
                self._start_fixed_voice_response(blocker, officer="FREYJA")
            else:
                self._start_freyja_trade_calculation(strategy)
            return

        if self._is_freyja_trade_cancel_request(question):
            blocker = self.active_trade_route.cancellation_warning()
            if blocker is not None:
                self._pending_freyja_cancel_confirmation = True
                self._start_fixed_voice_response(
                    blocker + self._t("freyja.voice.cancel_instruction"),
                    officer="FREYJA",
                    arm_after=True,
                )
                return
            cancelled = self.active_trade_route.cancel()
            self._start_fixed_voice_response(
                (
                    self._t("freyja.voice.cancelled")
                    if cancelled else
                    self._t("freyja.voice.no_route_cancel")
                ),
                officer="FREYJA",
            )
            return

        cockpit_intent = parse_cockpit_intent(question)
        if cockpit_intent is not None:
            self._reflex_engine().resolve(question)
            self._refresh_cockpit_state_now()
            if cockpit_intent.feature == "docking_request":
                self.command_memory.remember(
                    commander, question, "docking_request", {}
                )
                answer = self.docking_assist.request_station_docking()
            elif cockpit_intent.feature in {
                "night_vision", "cargo_scoop", "landing_gear", "hyperspace",
                "srv_lights", "srv_night_vision",
                "srv_cargo_scoop",
            }:
                state_name = (
                    "toggle" if cockpit_intent.requested_state is None
                    else "on" if cockpit_intent.requested_state else "off"
                )
                self.command_memory.remember(
                    commander, question, f"cockpit_{cockpit_intent.feature}",
                    {"state": state_name},
                )
                answer = self.docking_assist.control_cockpit_toggle(
                    cockpit_intent.feature, cockpit_intent.requested_state
                )
            else:
                answer = self.cockpit_advisor.describe(cockpit_intent)
            self.heimdall_diagnostics.record_cockpit_advice(
                cockpit_intent, self.cockpit_advisor.state, answer
            )
            self._last_voice_question = question
            self._last_learned_command = None
            self._start_fixed_voice_response(answer, officer="HEIMDALL")
            return

        lowered_question = question.casefold()
        if self._is_fsd_injection_authorization(question):
            self._start_fixed_voice_response(
                self.fsd_injections.authorize_pending_voice(), officer="HEIMDALL"
            )
            return
        injection_distance = self._fsd_injection_distance_request(question)
        if injection_distance is not None:
            jump_range = (
                self.navigation_manager.context.max_jump_range
                if self.navigation_manager is not None else 0.0
            )
            self._start_fixed_voice_response(
                self.fsd_injections.recommendation_voice(
                    injection_distance, jump_range
                ),
                officer="HEIMDALL",
            )
            return
        if self._is_route_injection_status_request(question):
            context = (
                self.navigation_manager.context
                if self.navigation_manager is not None else None
            )
            if context is None:
                answer = self._t("heimdall.voice.no_context")
            else:
                progress = context.route_progress()
                answer = self.fsd_injections.route_voice_summary(
                    context.route, progress.current_index, context.max_jump_range
                )
            self._start_fixed_voice_response(answer, officer="HEIMDALL")
            return
        if self._is_fsd_injection_status_request(lowered_question):
            self._start_fixed_voice_response(
                self.fsd_injections.voice_summary(), officer="HEIMDALL"
            )
            return
        if self._is_memory_confirmation(question):
            confirmed = bool(previous_question) and self.command_memory.confirm(
                commander, previous_question
            )
            self._start_fixed_voice_response(
                self._t("odin.memory.confirmed")
                if confirmed else self._t("odin.memory.no_previous")
            )
            return
        if self._is_memory_forget(question):
            forgotten = bool(previous_question) and self.command_memory.forget(
                commander, previous_question
            )
            self._last_learned_command = None
            self._start_fixed_voice_response(
                self._t("odin.memory.forgotten")
                if forgotten else self._t("odin.memory.not_found")
            )
            return

        corrected = self._memory_correction(question)
        if corrected and previous_question:
            learned = self._resolve_reflex_command(corrected)
            if learned is not None:
                self.command_memory.remember(
                    commander, previous_question, learned.intent, learned.payload
                )
                self._last_learned_command = learned
                self._start_fixed_voice_response(
                    self._t("odin.memory.correction_saved")
                )
            else:
                self._start_fixed_voice_response(
                    self._t("odin.memory.correction_unsafe")
                )
            return

        learned = self.command_memory.resolve(commander, question)
        if learned is None:
            learned = self._resolve_reflex_command(question)
            if learned is not None:
                self.command_memory.remember(
                    commander, question, learned.intent, learned.payload
                )
        self._last_voice_question = question
        self._last_learned_command = learned
        if learned is not None and learned.intent == "home_route":
            base = self.home_base_manager.current
            if base is None:
                self._start_fixed_voice_response(
                    self._t("heimdall.voice.no_base"),
                    officer="HEIMDALL",
                )
            else:
                self._start_voice_route(base.system)
            return
        if learned is not None and learned.intent == "neutron_route":
            self._start_voice_route(learned.payload["destination"])
            return
        if learned is not None and learned.intent == "freyja_trade_menu":
            self._open_freyja_trade_menu()
            return
        if learned is not None and learned.intent == "docking_request":
            self._refresh_cockpit_state_now()
            self._start_fixed_voice_response(
                self.docking_assist.request_station_docking(), officer="HEIMDALL"
            )
            return
        if learned is not None and learned.intent.startswith("cockpit_"):
            self._refresh_cockpit_state_now()
            state_name = learned.payload.get("state", "toggle")
            requested_state = (
                None if state_name == "toggle" else state_name == "on"
            )
            self._start_fixed_voice_response(
                self.docking_assist.control_cockpit_toggle(
                    learned.intent.removeprefix("cockpit_"), requested_state
                ),
                officer="HEIMDALL",
            )
            return

        if self.config.public_beta_no_ai:
            self._start_fixed_voice_response(
                "No entendí esa orden, comandante. Puede consultar la lista de comandos disponibles.",
                officer="ODIN",
            )
            return

        balance = (
            self.expedition_ledger.summary("consulta por voz")
            if self.expedition_ledger is not None else None
        )
        navigation = (
            self.navigation_manager.context
            if self.navigation_manager is not None else None
        )
        biology = self.scientific_context.system_predictions(
            self.commander_state.current_system
        )
        live_context = build_live_context(
            self.commander_state,
            navigation,
            balance,
            biology,
            self.home_base_manager.current.system
            if self.home_base_manager.current is not None else "",
            self.config.language,
        )
        officer_context = self.officer_broker.context(
            self.dashboard_snapshot, question, self._ai_allowed_officers()
        )
        context = (
            f"{live_context}\n\n{officer_context}"
            if self.config.ai_provider == "ollama" else officer_context
        )
        self._voice_busy.set()
        threading.Thread(
            target=self._run_voice_response,
            args=(question, context),
            name="odin-voice-conversation",
            daemon=True,
        ).start()

    def _refresh_cockpit_state_now(self) -> None:
        """Lee el estado actual antes de una acción para evitar copias obsoletas."""

        try:
            status = json.loads(self.config.status_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        cockpit_state = self.cockpit_advisor.update_status(status)
        self.docking_assist.update_status(cockpit_state)

    @staticmethod
    def _command_from_text(text: str) -> LearnedCommand | None:
        match = ReflexResolver().resolve(text, record=False)
        if match is None:
            return None
        return LearnedCommand(match.intent, dict(match.payload))

    def _resolve_reflex_command(self, text: str) -> LearnedCommand | None:
        match = self._reflex_engine().resolve(text)
        if match is None:
            return None
        return LearnedCommand(match.intent, dict(match.payload))

    def _reflex_engine(self) -> ReflexResolver:
        resolver = getattr(self, "reflex_resolver", None)
        if resolver is None:
            resolver = ReflexResolver()
            self.reflex_resolver = resolver
        return resolver

    @staticmethod
    def _is_memory_confirmation(text: str) -> bool:
        lowered = text.casefold()
        return any(term in lowered for term in (
            "eso esta bien", "eso está bien", "orden correcta", "that is right",
            "that's right", "that is correct", "correct command",
            "isso esta certo", "isso está certo", "ordem correta",
        ))

    @staticmethod
    def _is_memory_forget(text: str) -> bool:
        lowered = text.casefold()
        return any(term in lowered for term in (
            "olvida esa orden", "olvidá esa orden", "olvidate de esa orden",
            "forget that command", "forget this command", "esqueça essa ordem",
            "esqueca essa ordem", "esquece essa ordem",
        ))

    @staticmethod
    def _memory_correction(text: str) -> str | None:
        match = re.search(
            r"\b(?:(?:quise|queria|quería)\s+decir|i\s+meant|"
            r"eu\s+quis\s+dizer|eu\s+queria\s+dizer)\s+(.+)$",
            text, re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _is_fsd_injection_status_request(text: str) -> bool:
        lowered = text.casefold()
        mentions_injection = any(term in lowered for term in (
            "inyeccion", "inyección", "injection", "injeção", "injecao",
        )) and any(term in lowered for term in (
            "fsd", "salto", "jump", "sintesis", "síntesis", "synthesis",
            "síntese", "sintese",
        ))
        mentions_jump_synthesis = (
            any(term in lowered for term in ("material", "materials", "materiais"))
            and any(term in lowered for term in (
                "sintesis", "síntesis", "synthesis", "síntese", "sintese",
            ))
            and any(term in lowered for term in ("fsd", "salto", "jump"))
        )
        mentions_synthesis = any(term in lowered for term in (
            "sintesis", "síntesis", "synthesis", "síntese", "sintese",
        )) and any(term in lowered for term in ("fsd", "salto", "jump"))
        return mentions_injection or mentions_jump_synthesis or mentions_synthesis

    @staticmethod
    def _fsd_injection_distance_request(text: str) -> float | None:
        lowered = text.casefold()
        if not any(term in lowered for term in (
            "inyeccion", "inyección", "saltar", "salto", "alcanzar",
            "injection", "jump", "reach", "injeção", "injecao", "alcançar",
            "alcancar",
        )):
            return None
        match = re.search(
            r"(\d+(?:[\.,]\d+)?)\s*(?:años?\s+luz|anos?(?:\s+luz|-luz)|"
            r"light[ -]?years?|ly)\b",
            lowered,
        )
        if match is None:
            return None
        return float(match.group(1).replace(",", "."))

    @staticmethod
    def _is_route_injection_status_request(text: str) -> bool:
        lowered = text.casefold()
        return any(term in lowered for term in ("ruta", "route", "rota")) and any(
            term in lowered for term in (
                "inyeccion", "inyección", "injection", "injeção", "injecao",
                "sintesis", "síntesis", "synthesis", "síntese", "sintese",
            )
        )

    @staticmethod
    def _is_fsd_injection_authorization(text: str) -> bool:
        lowered = text.casefold()
        authorization = bool(re.search(
            r"\b(?:autorizo|confirmo|apruebo|authorize|authorise|confirm|approve|aprovo)\b",
            lowered,
        ))
        injection = bool(re.search(
            r"\b(?:inyeccion|inyección|injection|injeção|injecao)\b", lowered
        ))
        return authorization and injection and bool(re.search(r"\bfsd\b", lowered))

    def _open_freyja_trade_menu(self) -> None:
        self._pending_freyja_trade_menu = True
        self._start_fixed_voice_response(
            self._t("freyja.voice.menu"),
            officer="FREYJA",
            arm_after=True,
        )

    @staticmethod
    def _is_credible_voice_question(question: str) -> bool:
        words = re.findall(r"[a-záéíóúüñ]+", question.casefold())
        if len(words) >= 2:
            return True
        if not words:
            return False
        accepted_short_orders = {
            "activo", "activa", "ayuda", "base", "biología", "biologias",
            "biologías", "combustible", "créditos", "creditos", "estado",
            "geología", "geologia", "mímir", "mimir", "nave", "ruta", "saldo",
            "hipersalto", "inyección", "inyeccion", "síntesis", "sintesis",
            "active", "help", "biology", "credits", "fuel", "injection", "synthesis",
            "ship", "route", "status", "trade", "mining", "ativo", "ajuda",
            "biologia", "créditos", "creditos", "combustível", "combustivel",
            "nave", "rota", "comércio", "comercio", "mineração", "mineracao",
            "injeção", "injecao", "síntese", "sintese",
        }
        return words[0] in accepted_short_orders

    def _run_voice_response(self, question: str, context: str) -> None:
        acknowledgement_done = threading.Event()
        threading.Thread(
            target=self._run_processing_message,
            args=(
                "ODIN",
                self._processing_message_for(question, self.config.language),
                acknowledgement_done,
            ),
            name="odin-processing-message",
            daemon=True,
        ).start()
        try:
            conversation = VoiceConversation(self.config)
            answer = conversation.answer(question, context)
            answer = self._sanitize_current_system_references(question, answer)
            acknowledgement_done.wait()
            print(f"ODIN: {answer}\n")
            conversation.voice.speak("ODIN", answer)
        except (
            MicrophoneError, TranscriptionError, OllamaError, OpenAIError,
            VoiceServiceError,
        ) as error:
            print(f"\nConversación por voz no disponible: {error}\n")
        finally:
            acknowledgement_done.wait()
            self._voice_busy.clear()
            self.wake_listener.resume()

    @staticmethod
    def _processing_message_for(question: str, language: str = "es-419") -> str:
        lowered = question.casefold()
        if any(word in lowered for word in (
            "biolog", "especie", "muestra", "mímir", "mimir", "species",
            "sample", "amostra",
        )):
            return localized_text("voice.processing.science", language)
        if any(word in lowered for word in (
            "crédito", "credito", "nave", "combustible", "comandante",
            "credit", "ship", "fuel", "commander", "combustível", "combustivel",
        )):
            return localized_text("voice.processing.commander", language)
        if any(word in lowered for word in (
            "sistema", "planeta", "base de datos", "escane", "system",
            "planet", "database", "scan", "banco de dados",
        )):
            return localized_text("voice.processing.database", language)
        return localized_text("voice.processing.default", language)

    def _sanitize_current_system_references(self, question: str, answer: str) -> str:
        """Evita repetir por voz el nombre completo de la ubicación actual."""

        lowered = question.casefold()
        asks_for_name = (
            (any(word in lowered for word in ("sistema", "system")) and any(term in lowered for term in (
                "cómo se llama", "como se llama", "cuál es", "cual es",
                "en qué", "en que", "dónde estoy", "donde estoy",
                "what is", "which system", "where am i", "qual é", "qual e",
                "onde estou",
            )))
            or any(term in lowered for term in (
                "sistema actual", "current system", "sistema atual",
            ))
            or any(term in lowered for term in (
                "dónde estoy", "donde estoy", "where am i", "onde estou",
            ))
        )
        if asks_for_name:
            return answer
        system = self.commander_state.current_system.strip()
        if not system:
            return answer
        sanitized = answer
        known_bodies = self.scientific_context.system_predictions(system)
        for body in sorted(known_bodies, key=len, reverse=True):
            sanitized = re.sub(
                re.escape(body),
                planet_reference(system, body),
                sanitized,
                flags=re.IGNORECASE,
            )
        return re.sub(
            re.escape(system),
            self._t("voice.current_system"),
            sanitized,
            flags=re.IGNORECASE,
        )

    def _run_processing_message(
        self, officer: str, message: str, completed: threading.Event
    ) -> None:
        try:
            print(f"{officer}: {message}")
            OfficerVoiceService(self.config).speak(officer, message)
        except VoiceServiceError as error:
            print(f"Voz de {officer} no disponible: {error}\n")
        finally:
            completed.set()

    def _remember_scientific_report(self, report) -> None:
        message = self.scientific_context.record(
            self.commander_state.current_system,
            report,
            announce=not self._restoring_context,
        )
        if message is not None:
            self.event_bus.publish_internal(
                InternalEvent.VOICE_MESSAGE_READY,
                message,
            )

    def _start_voice_route(self, destination: str) -> None:
        if self.navigation_manager is None:
            self._route_calculation_busy.clear()
            self._start_fixed_voice_response(
                self._t("heimdall.voice.no_context"),
                officer="HEIMDALL",
            )
            return
        context = self.navigation_manager.context
        snapshot = NavigationContext(
            current_system=context.current_system,
            max_jump_range=context.max_jump_range,
        )
        self._voice_busy.set()
        self._route_calculation_busy.set()
        self._route_acknowledgement_done.clear()
        threading.Thread(
            target=self._run_processing_message,
            args=(
                "HEIMDALL",
                self._t("heimdall.voice.calculating"),
                self._route_acknowledgement_done,
            ),
            name="heimdall-processing-message",
            daemon=True,
        ).start()
        print("\n" + self._t(
            "heimdall.log.calculating_route",
            source=snapshot.current_system or self._t("heimdall.log.unknown_origin"),
            destination=destination,
        ))
        threading.Thread(
            target=self._calculate_voice_route,
            args=(snapshot, destination),
            name="heimdall-voice-route",
            daemon=True,
        ).start()

    def _calculate_voice_route(
        self, context: NavigationContext, destination: str
    ) -> None:
        try:
            plan = self.heimdall_route_planner.calculate_fastest(context, destination)
            self._route_results.put((plan, None))
        except (SpanshRouteError, ValueError) as error:
            self.heimdall_diagnostics.record_route_error(destination, error)
            self._route_results.put((None, "route_error"))

    def _finish_voice_route(self, plan, error: str | None) -> None:
        self._route_calculation_busy.clear()
        if error is not None:
            self._start_fixed_voice_response(
                self._t("heimdall.voice.route_error"),
                officer="HEIMDALL",
                wait_for=self._route_acknowledgement_done,
            )
            return
        try:
            self.heimdall_route_planner.activate(plan)
            self.heimdall_diagnostics.record_planned_route(plan)
            next_system = plan.next_waypoint.system if plan.next_waypoint else None
            answer = self._t(
                "heimdall.voice.route_summary", source=plan.source_system,
                destination=plan.destination_system,
                jumps=plan.actual_total_jumps, distance=f"{plan.distance:.0f}",
            )
            conventional = plan.conventional_minimum_jumps
            saved = plan.estimated_jumps_saved
            if conventional is not None and saved is not None:
                if saved > 0:
                    answer += self._t(
                        "heimdall.voice.route_saved", conventional=conventional,
                        saved=saved,
                    )
                else:
                    answer += self._t("heimdall.voice.route_not_better")
            if next_system:
                answer += self._t("heimdall.voice.copied", system=next_system)
            else:
                answer += self._t("heimdall.voice.arrived")
        except (OSError, RuntimeError, ValueError) as route_error:
            self.heimdall_diagnostics.record_route_error(
                getattr(plan, "destination_system", "desconocido"),
                route_error,
            )
            answer = self._t("heimdall.voice.activation_error")
        if (self.config.ai_provider == "ollama"
                or self.config.ai_share_navigation_data):
            report = {
                "source": getattr(plan, "source_system", ""),
                "destination": getattr(plan, "destination_system", ""),
                "jumps": getattr(plan, "actual_total_jumps", 0),
                "distance_ly": getattr(plan, "distance", 0),
                "conventional_jumps": getattr(plan, "conventional_minimum_jumps", None),
                "estimated_jumps_saved": getattr(plan, "estimated_jumps_saved", None),
                "next_system": next_system or "",
                "heimdall_summary": answer,
            }

            def deliver() -> None:
                self._route_acknowledgement_done.wait()
                self._officer_ai_results.put((
                    "Explicá la ruta calculada por HEIMDALL, indicando saltos, "
                    "distancia, ahorro estimado y siguiente sistema.",
                    "HEIMDALL", report,
                ))
                self._voice_busy.clear()

            threading.Thread(
                target=deliver, name="heimdall-ai-route-report", daemon=True
            ).start()
        else:
            self._start_fixed_voice_response(
                answer,
                officer="HEIMDALL",
                wait_for=self._route_acknowledgement_done,
            )

    def request_neutron_route(self, destination: str) -> bool:
        """Encola una ruta solicitada por la GUI para procesarla en el motor."""

        normalized = " ".join(str(destination).split())
        if (
            not normalized
            or self._route_calculation_busy.is_set()
            or not self._manual_route_requests.empty()
        ):
            return False
        self._manual_route_requests.put(normalized)
        return True

    def request_exact_route(self, destination: str) -> tuple[bool, str]:
        """Encola Galaxy Plotter con la física y carga actuales de la nave."""

        normalized = " ".join(str(destination).split())
        if not normalized:
            return False, "Ingresá un sistema de destino."
        if (
            self._route_calculation_busy.is_set()
            or not self._manual_route_requests.empty()
            or self._exact_route_calculation_busy.is_set()
            or not self._manual_exact_route_requests.empty()
        ):
            return False, "Ya hay una ruta en proceso. Esperá a que finalice."
        if self.navigation_manager is None:
            return False, "HEIMDALL todavía no tiene contexto de navegación."
        readiness = self.navigation_manager.context.exact_plotter_readiness()
        if not readiness["ready"]:
            missing = ", ".join(readiness["missing"])
            return False, f"Faltan datos de la nave para la ruta exacta: {missing}."
        cargo = int(
            getattr(getattr(self, "trade_profile", None), "cargo_used", 0) or 0
        )
        self._manual_exact_route_requests.put((normalized, cargo))
        return True, ""

    def _start_exact_route(self, destination: str, cargo: int) -> None:
        context = replace(self.navigation_manager.context)
        self._exact_route_calculation_busy.set()
        print(
            f"HEIMDALL: calculando ruta exacta desde {context.current_system} "
            f"hasta {destination} con {cargo} t de carga."
        )
        threading.Thread(
            target=self._calculate_exact_route,
            args=(context, destination, cargo),
            name="heimdall-exact-route", daemon=True,
        ).start()

    def _calculate_exact_route(
        self, context: NavigationContext, destination: str, cargo: int
    ) -> None:
        try:
            plan = self.heimdall_route_planner.calculate_exact(
                context, destination, cargo=cargo
            )
            self._exact_route_results.put((plan, None))
        except (SpanshRouteError, ValueError) as error:
            self.heimdall_diagnostics.record_route_error(destination, error)
            self._exact_route_results.put((None, "route_error"))

    def _finish_exact_route(
        self, plan: ExactRoutePlan | None, error: str | None
    ) -> None:
        self._exact_route_calculation_busy.clear()
        if error is not None or plan is None:
            print("HEIMDALL: no fue posible calcular la ruta exacta.")
            return
        try:
            self.heimdall_route_planner.activate(plan)
            self.heimdall_diagnostics.record_planned_route(plan)
            next_system = plan.next_waypoint.system if plan.next_waypoint else ""
            print(
                f"HEIMDALL: ruta exacta calculada: {plan.total_jumps} saltos, "
                f"{plan.distance:.0f} años luz. "
                + (f"Siguiente sistema: {next_system}." if next_system else "Destino alcanzado.")
            )
        except (OSError, RuntimeError, ValueError) as route_error:
            self.heimdall_diagnostics.record_route_error(
                plan.destination_system, route_error
            )
            print("HEIMDALL: la ruta exacta fue calculada pero no pudo activarse.")

    def _start_fixed_voice_response(
        self,
        answer: str,
        *,
        officer: str = "ODIN",
        wait_for: threading.Event | None = None,
        arm_after: bool = False,
    ) -> None:
        self._voice_busy.set()
        threading.Thread(
            target=self._run_fixed_voice_response,
            args=(officer, answer, wait_for, arm_after),
            name=f"{officer.lower()}-fixed-voice-response",
            daemon=True,
        ).start()

    def _handle_unclear_voice_command(self) -> None:
        """Permite un solo reintento y luego cierra la sesión de escucha."""
        if not self._voice_retry_pending:
            self._voice_retry_pending = True
            self._start_fixed_voice_response(
                self._t("voice.unclear_retry"),
                arm_after=True,
            )
            return

        self._voice_retry_pending = False
        self.wake_listener.armed.clear()
        self._start_fixed_voice_response(
            self._t("voice.unclear_close")
        )

    def _run_fixed_voice_response(
        self,
        officer: str,
        answer: str,
        wait_for: threading.Event | None = None,
        arm_after: bool = False,
    ) -> None:
        try:
            if wait_for is not None:
                wait_for.wait()
            print(f"{officer}: {answer}\n")
            OfficerVoiceService(self.config).speak(officer, answer)
        except VoiceServiceError as error:
            print(f"Voz de {officer} no disponible: {error}\n")
        finally:
            self._voice_busy.clear()
            if arm_after:
                self.wake_listener.arm()
            self.wake_listener.resume()

    @staticmethod
    def _is_freyja_trade_request(text: str) -> bool:
        return is_trade_menu_request(text)

    @staticmethod
    def _brokk_mining_request(text: str) -> str | None:
        normalized = re.sub(
            r"[^a-z0-9áéíóúüñ]+", " ", str(text).casefold()
        ).strip()
        match = re.search(
            r"\b(?:quiero|vamos a|deseo|necesito|busca(?:me)?|quero|vamos|"
            r"preciso|procura(?:r)?|i want to|let(?: s|s)?|please|find)\s+"
            r"(?:minar|minerar|mine|mining)\s+(.+)$",
            normalized,
        )
        if not match:
            match = re.search(
                r"\bbrokk\s+(?:(?:quiero|quero|i want to)\s+)?"
                r"(?:minar|minerar|mine)\s+(.+)$", normalized
            )
        if not match:
            return None
        mineral = re.sub(
            r"\b(?:por favor|comandante|please|commander)\b.*$", "", match.group(1)
        ).strip()
        return mineral or None

    @staticmethod
    def _is_brokk_status_request(text: str) -> bool:
        normalized = re.sub(
            r"[^a-z0-9áéíóúüñ]+", " ", str(text).casefold()
        ).strip()
        mining = bool(re.search(r"\b(?:brokk|minera|minería|mineria|minando|mineração|mineracao|mining)\b", normalized))
        status = bool(re.search(
            r"\b(?:estado|resumen|progreso|rendimiento|cuanto|cuánto|carga|"
            r"status|summary|progress|performance|how much|cargo|resumo|"
            r"progresso|rendimento|quanto)\b",
            normalized,
        ))
        return mining and status

    @staticmethod
    def _is_brokk_sale_request(text: str) -> bool:
        normalized = re.sub(
            r"[^a-z0-9áéíóúüñ]+", " ", str(text).casefold()
        ).strip()
        sale = bool(re.search(r"\b(?:vender|vendo|venta|vendemos|sell|selling|sale)\b", normalized))
        cargo = bool(re.search(
            r"\b(?:brokk|mineral(?:es)?|minera|minería|mineria|mineração|mineracao|mining|carga|cargo)\b",
            normalized,
        ))
        destination = bool(re.search(
            r"\b(?:donde|dónde|destino|buscar|busca|mejor|where|destination|find|best|onde|procurar|melhor)\b", normalized
        ))
        return sale and cargo and destination

    def _brokk_sale_voice_summary(self) -> str:
        processor = self.brokk_processor
        if processor is None:
            return self._t("brokk.voice.unavailable")
        session = processor.session
        valuation = session.valuation if isinstance(session.valuation, dict) else {}
        destination = valuation.get("best_permanent", {}) or {}
        if destination:
            station = destination.get("station", self._t("brokk.voice.recommended_station"))
            system = destination.get("system", self._t("brokk.voice.indicated_system"))
            unit_price = max(0, int(destination.get("unit_price", 0) or 0))
            distance = max(0.0, float(destination.get("distance_ly", 0) or 0))
            return self._t(
                "brokk.voice.sale_result", station=station, system=system,
                price=unit_price, distance=f"{distance:.1f}",
            )
        if valuation.get("error"):
            return self._t("brokk.voice.no_sale")
        if not session.cargo_inventory:
            return self._t("brokk.voice.no_cargo")
        if self._mining_valuation_busy.is_set():
            return self._t("brokk.voice.sale_busy")
        return self._t("brokk.voice.no_valuation")

    def _brokk_voice_summary(self) -> str:
        processor = self.brokk_processor
        if processor is None:
            return self._t("brokk.voice.unavailable")
        session = processor.session
        if not session.started_at and not session.produced:
            return self._t("brokk.voice.no_operation")
        performance = calculate_mining_performance(
            session, self._mining_duration_hours(session)
        )
        target = (
            self._t("brokk.voice.target", target=session.target_mineral)
            if session.target_mineral else ""
        )
        return self._t(
            "brokk.voice.summary", status=self._t(f"brokk.status.{session.status}"), target=target,
            produced=f"{performance.produced_tonnes:g}",
            rate=f"{performance.tonnes_per_hour:g}", cargo=session.refined_total,
        )

    @staticmethod
    def _freyja_powerplay_sale_request(text: str) -> str | None:
        normalized = re.sub(
            r"[^a-z0-9áéíóúüñ]+",
            " ", text.casefold(),
        ).strip()
        if not re.search(r"\b(?:vend(?:er|o|amos|e)|sell)\b", normalized):
            return None
        if not any(word in normalized for word in (
            "powerplay", "power play", "refuerzo", "reinforcement", "potencia", "reforço", "reforco",
        )):
            return None
        match = re.search(
            r"\b(?:vend(?:er|o|amos|e)|sell)\s+(.+?)\s+"
            r"(?:en|in|em)\s+(?:(?:un|a|um)\s+)?(?:sistema|system)\b",
            normalized,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _is_eddn_status_request(text: str) -> bool:
        lowered = text.casefold()
        return "eddn" in lowered and bool(re.search(
            r"\b(?:estado|funciona|activo|activa|transmisi[oó]n|env[ií]os?|datos|"
            r"status|working|active|transmission|uploads?|data|funcionando|"
            r"transmiss[aã]o|envios?)\b",
            lowered,
        ))

    @staticmethod
    def _eddn_startup_status(
        capture_enabled: bool, upload_enabled: bool, test_mode: bool
    ) -> str:
        if not capture_enabled:
            state = "desactivado"
        elif not upload_enabled:
            state = "captura local, sin transmisión"
        elif test_mode:
            state = "transmisión de pruebas"
        else:
            state = "transmisión pública activa"
        return f"EDDN                  : {state}"

    @staticmethod
    def _eddn_voice_summary(
        summary: EDDNOutboxSummary, capture_enabled: bool, upload_enabled: bool,
        language: str = "es-419",
    ) -> str:
        if not capture_enabled:
            return localized_text("odin.eddn.capture_off", language)
        if not upload_enabled:
            return localized_text("odin.eddn.upload_off", language, pending=summary.pending)
        last = (
            localized_text("odin.eddn.last_sent", language, event=summary.last_sent_event)
            if summary.last_sent_event else
            localized_text("odin.eddn.none_sent", language)
        )
        return localized_text(
            "odin.eddn.active", language, sent=summary.sent,
            pending=summary.pending, retrying=summary.retrying,
            rejected=summary.rejected,
        ) + last

    @staticmethod
    def _is_freyja_trade_status_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(r"\b(?:estado|progreso|status|progress)\b.*\b(?:ruta comercial|trade route|rota comercial)\b", lowered)
            or re.search(r"\b(?:qu[eé]|what|o que)\s+(?:(?:tengo|do i have|tenho)\s+(?:que|to|de)\s+)?(?:comprar|vender|buy|sell)\b", lowered)
            or any(term in lowered for term in ("siguiente tramo", "next leg", "próximo trecho", "proximo trecho"))
            or bool(re.search(r"\brepet(?:i|í|ir)\b.*\b(?:instrucci[oó]n|tramo)\b", lowered))
            or bool(re.search(
                r"\b(?:beneficio|ganancia)\b.*\bruta\b|\bruta\b.*\b(?:beneficio|ganancia)\b",
                lowered,
            ))
            or any(term in lowered for term in ("tramos quedan", "legs remain", "trechos faltam"))
        )

    @staticmethod
    def _is_freyja_trade_ledger_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:beneficio|ganancia|invert[ií]|ventas?|vendido|profit|"
                r"earnings|invested|sales?|sold|lucro|ganho|investido|vendas?)\b",
                lowered,
            )
            and re.search(r"\b(?:comercio|comercial|comerciando|llevo|trade|trading|negócio|negocio)\b", lowered)
        )

    @staticmethod
    def _freyja_ledger_voice_summary(summary: TradeSummary, language: str = "es-419") -> str:
        return localized_text(
            "freyja.voice.ledger", language, invested=summary.invested,
            revenue=summary.revenue, profit=summary.realized_profit,
            cargo=summary.cargo_units,
        )

    @staticmethod
    def _is_freyja_trade_cancel_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:cancela|cancelá|cancelar|abandona|abandoná|cancel|abandon)\b"
                r".*\b(?:ruta comercial|trade route|rota comercial)\b",
                lowered,
            )
        )

    @staticmethod
    def _is_voice_listening_cancel(text: str) -> bool:
        normalized = " ".join(str(text or "").casefold().strip().split())
        return bool(re.search(
            r"\b(?:silencio|cancelar|cancela|cancelá|cerrar|cierra|cerrá|detener|deten[eé])\b"
            r"(?:\s+(?:la\s+)?(?:escucha|orden|voz|comando))?\s*$",
            normalized,
        ))

    @staticmethod
    def _ai_plan_objective(text: str) -> str | None:
        normalized = " ".join(str(text or "").strip().split())
        match = re.search(
            r"\b(?:crea|creá|crear|prepara|prepará|preparar|arma|armá|armar)\s+"
            r"(?:un\s+)?plan(?:\s+(?:para|de))?\s+(?P<objective>.+)$",
            normalized, flags=re.IGNORECASE,
        )
        if match:
            objective = match.group("objective").strip(" ,.;:!?\"")
            return normalize_engineering_objective(objective) or None
        engineering = normalize_engineering_objective(normalized)
        return engineering if engineering != normalized else None

    @staticmethod
    def _engineer_unlock_spoken_name(text: str) -> str:
        match = re.search(
            r"\b(?:quiero\s+)?(?:desbloquear|desbloquea|desbloqueá|habilitar|liberar)\s+"
            r"(?:a\s+|al\s+)?(?:el\s+|la\s+)?(?:ingeniero|ingeniera)?\s*(?P<name>.+)$",
            str(text or ""), flags=re.IGNORECASE,
        )
        return match.group("name").strip(" ,.;:!?\"") if match else ""

    @staticmethod
    def _is_affirmative_voice_answer(text: str) -> bool:
        return bool(re.search(
            r"\b(?:s[ií]|correcto|correcta|confirmo|exacto|ese|esa|afirmativo)\b",
            str(text or ""), flags=re.IGNORECASE,
        ))

    @staticmethod
    def _is_nearby_station_request(text: str) -> bool:
        lowered = str(text or "").casefold()
        place = re.search(
            r"\b(?:estaci(?:[oó]n|ones)|bases?|puertos?|starports?|stations?)\b",
            lowered,
        )
        proximity = re.search(
            r"\b(?:cercan[ao]|m[aá]s\s+cercan[ao]|pr[oó]xim[ao]|nearest|nearby)\b",
            lowered,
        )
        compatibility = re.search(
            r"\b(?:aterrizar|atracar|plataforma|nave\s+grande|landing|dock|large\s+pad)\b",
            lowered,
        )
        current_system = re.search(
            r"\b(?:en|de)\s+(?:este|el)\s+sistema\b|\b(?:sistema\s+actual)\b",
            lowered,
        )
        return bool(place and (proximity or compatibility or current_system))

    @staticmethod
    def _powerplay_activity_request(text: str) -> tuple[str, str] | None:
        """Reconoce pedidos naturales de actividades Powerplay por voz."""

        lowered = str(text or "").casefold()
        if not re.search(r"\bpower\s*play\b|\bpowerplay\b", lowered):
            return None
        activity_patterns = (
            ("combat", r"\b(?:combates?|combatir|batallas?|conflictos?|combat)\b"),
            ("mining", r"\b(?:miner[ií]a|minar|mineral|mining)\b"),
            ("trade", r"\b(?:comercio|comerciar|mercanc[ií]a|trade)\b"),
            ("transport", r"\b(?:transporte|transportar|entrega|transport)\b"),
            ("exploration", r"\b(?:exploraci[oó]n|explorar|exploration)\b"),
            ("on_foot", r"\b(?:a\s+pie|infanter[ií]a|on\s+foot)\b"),
            ("salvage", r"\b(?:rescate|salvamento|salvage)\b"),
        )
        for activity, pattern in activity_patterns:
            if re.search(pattern, lowered):
                return activity, ""
        return None

    @staticmethod
    def _is_current_system_station_request(text: str) -> bool:
        lowered = str(text or "").casefold()
        place = re.search(
            r"\b(?:estaci(?:[oó]n|ones)|bases?|puertos?|starports?|stations?)\b",
            lowered,
        )
        scope = re.search(
            r"\b(?:en|de)\s+(?:este|el)\s+sistema\b|\b(?:sistema\s+actual)\b",
            lowered,
        )
        return bool(place and scope)

    def _start_ai_station_search(self, question: str) -> None:
        position = self.commander_state.star_position
        if position is None:
            self._start_fixed_voice_response(
                self._t("freyja.voice.no_coordinates"), officer="FREYJA"
            )
            return
        requires_large_pad = bool(
            getattr(self.trade_profile, "requires_large_pad", False)
        )
        allow_planetary = not bool(re.search(
            r"\b(?:sin|no)\s+(?:bases?\s+)?planetari",
            question, flags=re.IGNORECASE,
        ))
        current_system_only = self._is_current_system_station_request(question)
        self._voice_busy.set()

        def worker() -> None:
            acknowledgement_done = threading.Event()
            threading.Thread(
                target=self._run_processing_message,
                args=("ODIN", self._t("ai.station_searching"), acknowledgement_done),
                name="freyja-station-search-message", daemon=True,
            ).start()
            try:
                if current_system_only:
                    stations = self._freyja_station_finder.in_system(
                        tuple(position), self.commander_state.current_system,
                        requires_large_pad=False,
                        allow_planetary=allow_planetary, limit=20,
                    )
                else:
                    stations = self._freyja_station_finder.nearest(
                        tuple(position), requires_large_pad=requires_large_pad,
                        allow_planetary=allow_planetary, limit=3,
                    )
                report = {
                    "officer": "FREYJA",
                    "query": ("stations_in_current_system" if current_system_only
                              else "nearest_compatible_station"),
                    "requires_large_pad": requires_large_pad,
                    "allow_planetary": allow_planetary, "results": stations,
                }
                if (self.config.public_beta_no_ai
                        or (self.config.ai_provider != "ollama"
                        and not self.config.ai_share_station_search_data)):
                    answer = self._station_search_local_answer(stations)
                    acknowledgement_done.wait()
                    print(f"FREYJA: {answer}")
                    OfficerVoiceService(self.config).speak("FREYJA", answer)
                    return
                context = (
                    self.officer_broker.context(
                        self.dashboard_snapshot, question, self._ai_allowed_officers()
                    )
                    + "\n\nINFORME NUEVO SOLICITADO A FREYJA:\n"
                    + json.dumps(report, ensure_ascii=False, default=str)
                )
                conversation = VoiceConversation(self.config)
                answer = conversation.answer(question, context)
                acknowledgement_done.wait()
                print(
                    f"FREYJA → IA DE ODIN: {len(stations)} estaciones compatibles.\n"
                    f"ODIN: {answer}\n"
                )
                conversation.voice.speak("ODIN", answer)
            except (MarketSourceError, OpenAIError, OllamaError, VoiceServiceError) as error:
                acknowledgement_done.wait()
                print(f"FREYJA: búsqueda de estación no disponible: {error}")
                try:
                    OfficerVoiceService(self.config).speak(
                        "FREYJA", self._t("ai.station_failed")
                    )
                except VoiceServiceError:
                    pass
            finally:
                acknowledgement_done.wait()
                self._voice_busy.clear()

        threading.Thread(
            target=worker, name="odin-ai-station-delegation", daemon=True
        ).start()

    @staticmethod
    def _is_freyja_trade_cancel_confirmation(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:confirmo|confirm|confirmo a)\b.*\b(?:cancelaci[oó]n comercial|trade cancellation|cancelamento comercial)\b",
                lowered,
            )
        )

    @staticmethod
    def _is_freyja_trade_recalculate_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:recalcula|recalculá|recalcular|actualiza|actualizá|recalculate|update)\b"
                r".*\b(?:ruta comercial|trade route|rota comercial)\b",
                lowered,
            )
        )

    @staticmethod
    def _freyja_trade_selection(text: str) -> str | None:
        lowered = text.casefold()
        if re.search(r"\b(?:1|uno|um|one|primera|primeira|first|rapida|r\u00e1pida|quick|rápida)\b", lowered):
            return "quick"
        if re.search(r"\b(?:2|dos|dois|two|segunda|second|tres estaciones|three stations|três estações|tres estacoes|circuito)\b", lowered):
            return "three_station"
        if re.search(r"\b(?:3|tres|três|three|tercera|terceira|third|treinta saltos|thirty jumps|trinta saltos|expedicion|expedici\u00f3n|expedition|expedição|expedicao)\b", lowered):
            return "expedition"
        if re.search(r"\b(?:4|cuatro|quatro|four|cuarta|quarta|fourth|powerplay|meritos|m\u00e9ritos|merits)\b", lowered):
            return "powerplay"
        return None

    def _start_freyja_trade_calculation(
        self, selection: str, preferred_commodity: str = "",
        allow_planetary: bool = True,
    ) -> None:
        self._trade_calculation_busy.set()
        self._trade_requested_strategy = selection
        self._voice_busy.set()
        print(f"FREYJA: {self._t('freyja.voice.consulting_bubble')}\n")
        threading.Thread(
            target=self._run_freyja_trade_calculation,
            args=(selection, preferred_commodity, allow_planetary),
            name=f"freyja-{selection}-calculation",
            daemon=True,
        ).start()

    def _run_freyja_trade_calculation(
        self, selection: str, preferred_commodity: str = "",
        allow_planetary: bool = True,
    ) -> None:
        trade_database = DatabaseManager(self.config.data_root)
        try:
            self._announce_freyja_trade_start(selection)
            trade_database.connect()
            trade_database.create_tables()
            self._calculate_freyja_trade(
                selection, MarketCache(trade_database), preferred_commodity,
                allow_planetary=allow_planetary,
            )
        except Exception:
            self._start_fixed_voice_response(
                self._t("freyja.voice.calculation_error"),
                officer="FREYJA",
            )
        finally:
            trade_database.disconnect()
            self._trade_calculation_busy.clear()
            self._trade_requested_strategy = ""
            self._trade_requested_commodity = ""

    def request_trade_calculation(
        self, selection: str, preferred_commodity: str = "",
        allow_planetary: bool = True,
    ) -> bool:
        """Encola desde la interfaz uno de los cuatro modelos de FREYJA."""

        allowed = {"quick", "three_station", "expedition", "powerplay"}
        if (
            selection not in allowed
            or self._trade_calculation_busy.is_set()
            or not self._manual_trade_requests.empty()
        ):
            return False
        commodity = " ".join(str(preferred_commodity).casefold().split())
        self._powerplay_sale_result = {}
        self._trade_requested_strategy = selection
        self._trade_requested_commodity = commodity
        self._manual_trade_requests.put((selection, commodity, bool(allow_planetary)))
        return True

    def control_mining_session(
        self, action: str, target_mineral: str = "", technique: str = "laser",
    ) -> str:
        """Controla desde la GUI el ciclo persistente de una operacion minera."""

        processor = self.brokk_processor
        if processor is None:
            return "BROKK no esta disponible."
        action = str(action).casefold().strip()
        target = " ".join(str(target_mineral).strip().split())
        technique = str(technique).casefold().strip()
        technique_labels = {
            "laser": "laser de superficie", "abrasion": "abrasion",
            "subsurface": "subsuperficie", "core": "nucleo profundo",
        }
        if technique not in technique_labels:
            technique = "laser"
        if action == "start":
            processor.start(
                system=self.commander_state.current_system,
                body=processor.session.body,
                technique=technique,
                target_mineral=target,
                technique_source="commander",
            )
            label = technique_labels[technique]
            return (
                f"Operacion minera por {label} preparada para {target}."
                if target else f"Operacion minera por {label} preparada."
            )
        if action == "pause":
            processor.pause()
            return "Operacion minera pausada."
        if action == "close":
            processor.close()
            return "Operacion minera cerrada; el historial fue conservado."
        return "Control minero no reconocido."

    def request_mining_search(self, mineral: str, ai_question: str = "") -> bool:
        """Busca hotspots conocidos sin bloquear el Journal ni la interfaz."""

        mineral = " ".join(str(mineral).split())
        origin = " ".join(str(self.commander_state.current_system).split())
        if not mineral or not origin or self._mining_search_busy.is_set():
            return False
        query = normalize_mineral_query(mineral)
        self._mining_search_busy.set()
        self._mining_search_result = {
            "mineral": mineral, "query": query, "status": "Consultando Spansh",
            "options": {}, "error": "",
        }

        def worker() -> None:
            try:
                locations = self._mining_search_client.locations(origin, query)
                options = select_mining_distance_tiers(locations)
                self._mining_search_result = {
                    "mineral": mineral, "query": query,
                    "status": "Listo" if options else "Sin zonas conocidas",
                    "options": {
                        tier: location.to_dict()
                        for tier, location in options.items()
                    },
                    "error": "" if options else (
                        "No encontré hotspots conocidos dentro de 900 años luz."
                    ),
                }
            except MiningSearchError:
                self._mining_search_result = {
                    "mineral": mineral, "query": query, "options": {},
                    "status": "Error",
                    "error": "No fue posible consultar las zonas mineras comunitarias.",
                }
            finally:
                self._mining_search_busy.clear()
                if ai_question:
                    report = dict(self._mining_search_result)
                    if (not self.config.public_beta_no_ai
                            and (self.config.ai_provider == "ollama"
                            or self.config.ai_share_mining_data)):
                        self._officer_ai_results.put((ai_question, "BROKK", report))
                    else:
                        self._officer_ai_results.put((
                            ai_question, "BROKK",
                            {"local_answer": self._brokk_search_local_answer(report)},
                        ))

        threading.Thread(target=worker, name="odin-brokk-search", daemon=True).start()
        return True

    def _start_ai_officer_report_response(
        self, question: str, officer: str, report: dict
    ) -> None:
        """Entrega un resultado especializado a la IA para redactar la respuesta."""

        local_answer = str(report.get("local_answer", "") or "").strip()
        if local_answer:
            self._start_fixed_voice_response(local_answer, officer=officer)
            return
        self._voice_busy.set()

        def worker() -> None:
            acknowledgement_done = threading.Event()
            threading.Thread(
                target=self._run_processing_message,
                args=(
                    "ODIN",
                    self._t("ai.officer_report_processing", officer=officer),
                    acknowledgement_done,
                ),
                name="odin-officer-report-message", daemon=True,
            ).start()
            try:
                context = (
                    self.officer_broker.context(
                        self.dashboard_snapshot, question, self._ai_allowed_officers()
                    )
                    + f"\n\nINFORME NUEVO ENTREGADO POR {officer}:\n"
                    + json.dumps(report, ensure_ascii=False, default=str)
                )
                conversation = VoiceConversation(self.config)
                answer = conversation.answer(question, context)
                acknowledgement_done.wait()
                print(f"{officer} → IA DE ODIN: informe recibido.")
                print(f"ODIN: {answer}\n")
                conversation.voice.speak("ODIN", answer)
            except (OpenAIError, OllamaError, VoiceServiceError) as error:
                acknowledgement_done.wait()
                print(f"ODIN IA: no pudo interpretar el informe de {officer}: {error}")
                try:
                    OfficerVoiceService(self.config).speak(
                        "ODIN", self._t("ai.officer_report_failed", officer=officer)
                    )
                except VoiceServiceError:
                    pass
            finally:
                acknowledgement_done.wait()
                self._voice_busy.clear()

        threading.Thread(
            target=worker, name=f"odin-ai-{officer.casefold()}-report", daemon=True
        ).start()

    def _brokk_search_local_answer(self, report: dict) -> str:
        error = str(report.get("error", "") or "").strip()
        if error:
            return error
        options = report.get("options", {}) or {}
        if not options:
            return self._t("brokk.voice.search_failed")
        labels = {"short": "corta", "medium": "media", "long": "larga"}
        parts = []
        for tier, option in options.items():
            parts.append(
                f"distancia {labels.get(tier, tier)}, {option.get('system', 'sin sistema')}, "
                f"a {float(option.get('distance_ly', 0) or 0):.1f} años luz"
            )
        return "BROKK encontró estas opciones: " + "; ".join(parts) + "."

    def select_mining_destination(self, tier: str) -> bool:
        option = self._mining_search_result.get("options", {}).get(str(tier), {})
        system = " ".join(str(option.get("system", "")).split())
        if not system:
            return False
        self.event_bus.publish_internal(
            InternalEvent.MINING_DESTINATION_SELECTED,
            {"system": system, "tier": tier, "source": "BROKK"},
        )
        return True

    def _handle_mining_destination_selected(self, payload: dict) -> None:
        system = str(payload.get("system", ""))
        if self.request_neutron_route(system):
            print(f"BROKK entregó {system} a HEIMDALL para calcular la ruta.")

    def _handle_mining_cargo_ready(self, payload: dict) -> None:
        """Conserva localmente el manifiesto que FREYJA podrá valorar."""

        cargo = payload.get("cargo", {}) if isinstance(payload, dict) else {}
        if not isinstance(cargo, dict) or not cargo:
            return
        self._mining_sale_manifest = {
            "system": str(payload.get("system", "")),
            "body": str(payload.get("body", "")),
            "cargo": {
                str(name): max(0, int(quantity or 0))
                for name, quantity in cargo.items()
                if int(quantity or 0) > 0
            },
            "produced": dict(payload.get("produced", {}) or {}),
            "transferred_to_carrier": dict(
                payload.get("transferred_to_carrier", {}) or {}
            ),
            "source": "BROKK",
            "status": "Esperando orden para buscar venta",
        }

    def request_guardian_search(self, module_key: str) -> bool:
        """Busca destinos sólo tras la acción explícita del comandante."""

        if self._guardian_search_busy.is_set():
            return False
        position = tuple(self.commander_state.star_position or ())
        modules = self.guardian_unlocks.snapshot().get("modules", {})
        module = modules.get(str(module_key), {})
        if len(position) != 3 or not module:
            self._guardian_plan = {
                "error": "No conozco todavía la posición galáctica actual.",
                "collection": [], "broker": {},
            }
            return False
        self._guardian_search_busy.set()
        self._guardian_plan = {
            "module_key": module_key, "collection": [], "broker": {},
            "error": "", "status": "Consultando Spansh",
        }

        def worker() -> None:
            try:
                plan = self.guardian_search.plan(module, position)
                self._guardian_plan = {**plan, "module_key": module_key, "status": "Listo"}
                self.guardian_plan_store.save(self._guardian_plan)
            except GuardianSearchError:
                self._guardian_plan = {
                    "module_key": module_key, "collection": [], "broker": {},
                    "error": "No fue posible consultar la base comunitaria.",
                    "status": "Error",
                }
            except Exception as error:
                self._guardian_plan = {
                    "module_key": module_key, "collection": [], "broker": {},
                    "error": "Falló el cálculo de destinos Guardian.",
                    "diagnostic": f"{type(error).__name__}: {error}",
                    "status": "Error",
                }
            finally:
                self._guardian_search_busy.clear()

        threading.Thread(target=worker, name="odin-guardian-search", daemon=True).start()
        return True

    def select_engineering_plan(self, plan_key: str) -> bool:
        """Guarda una meta informativa; no fabrica ni modifica módulos."""

        return self.engineering.select_plan(str(plan_key))

    def request_ai_plan(self, objective: str, announce: bool = False) -> bool:
        """Genera un plan consultivo sin bloquear la interfaz ni ejecutar acciones."""

        if self.config.public_beta_no_ai:
            return False
        objective = normalize_engineering_objective(
            str(objective or "").strip(), self.engineering.voice_aliases
        )
        if not objective or self._ai_plan_busy.is_set():
            return False
        self._ai_plan_busy.set()
        self._ai_plan_error = ""

        def worker() -> None:
            try:
                snapshot = dict(self.dashboard_snapshot or {})
                snapshot.pop("ai", None)
                context = self.officer_broker.context(
                    snapshot, objective, self._ai_allowed_officers()
                )
                plan = self.ai_coordinator.propose(objective, context=context)
                self._ai_plan_results.put((plan, "", announce))
            except (RuntimeError, ValueError, TypeError) as error:
                self._ai_plan_error = str(error)
                self._ai_plan_results.put((None, self._ai_plan_error, announce))
            except Exception:
                self._ai_plan_error = self._t("ai.unavailable")
                self._ai_plan_results.put((None, self._ai_plan_error, announce))
                logging.getLogger(__name__).exception("AI_PLAN_FAILED")
            finally:
                self._ai_plan_busy.clear()

        threading.Thread(
            target=worker, name="odin-ai-coordinator", daemon=True
        ).start()
        return True

    def request_ai_answer(self, question: str) -> bool:
        """Consulta escrita no intrusiva usando informes de oficiales autorizados."""

        if self.config.public_beta_no_ai:
            return False
        question = " ".join(str(question or "").strip().split())
        if not question or self._ai_answer_busy.is_set():
            return False
        if self._is_nearby_station_request(question):
            return self._request_written_station_answer(question)
        self._ai_answer_busy.set()
        self._ai_answer_state = {
            "question": question, "answer": "", "error": "", "model": "",
        }

        def worker() -> None:
            try:
                context = self.officer_broker.context(
                    self.dashboard_snapshot, question, self._ai_allowed_officers()
                )
                reply = self.ai_coordinator.assistant.ask(question, context=context)
                self._ai_answer_state = {
                    "question": question, "answer": reply.text, "error": "",
                    "model": str(getattr(reply, "model", "")),
                }
                print(f"CONSULTA IA: {question}\nODIN: {reply.text}\n")
            except (OpenAIError, OllamaError, RuntimeError, ValueError) as error:
                self._ai_answer_state = {
                    "question": question, "answer": "", "error": str(error),
                    "model": "",
                }
            finally:
                self._ai_answer_busy.clear()

        threading.Thread(
            target=worker, name="odin-ai-written-query", daemon=True
        ).start()
        return True

    def _request_written_station_answer(self, question: str) -> bool:
        """Delega a FREYJA una búsqueda real y devuelve el resultado por texto."""

        position = self.commander_state.star_position
        if position is None:
            self._ai_answer_state = {
                "question": question, "answer": "",
                "error": self._t("freyja.voice.no_coordinates"), "model": "",
            }
            return True
        self._ai_answer_busy.set()
        self._ai_answer_state = {
            "question": question, "answer": "", "error": "", "model": "",
        }
        requires_large_pad = bool(
            getattr(self.trade_profile, "requires_large_pad", False)
        )
        allow_planetary = not bool(re.search(
            r"\b(?:sin|no)\s+(?:bases?\s+)?planetari",
            question, flags=re.IGNORECASE,
        ))
        current_system_only = self._is_current_system_station_request(question)

        def worker() -> None:
            try:
                if current_system_only:
                    stations = self._freyja_station_finder.in_system(
                        tuple(position), self.commander_state.current_system,
                        requires_large_pad=False,
                        allow_planetary=allow_planetary, limit=20,
                    )
                else:
                    stations = self._freyja_station_finder.nearest(
                        tuple(position), requires_large_pad=requires_large_pad,
                        allow_planetary=allow_planetary, limit=3,
                    )
                report = {
                    "officer": "FREYJA",
                    "query": ("stations_in_current_system" if current_system_only
                              else "nearest_compatible_station"),
                    "requires_large_pad": requires_large_pad,
                    "allow_planetary": allow_planetary, "results": stations,
                }
                if (self.config.ai_provider != "ollama"
                        and not self.config.ai_share_station_search_data):
                    self._ai_answer_state = {
                        "question": question,
                        "answer": self._station_search_local_answer(stations),
                        "error": "", "model": "local",
                    }
                    return
                context = (
                    self.officer_broker.context(
                        self.dashboard_snapshot, question, self._ai_allowed_officers()
                    )
                    + "\n\nINFORME NUEVO SOLICITADO A FREYJA:\n"
                    + json.dumps(report, ensure_ascii=False, default=str)
                )
                reply = self.ai_coordinator.assistant.ask(question, context=context)
                self._ai_answer_state = {
                    "question": question, "answer": reply.text, "error": "",
                    "model": str(getattr(reply, "model", "")),
                }
                print(
                    f"CONSULTA IA: {question}\n"
                    f"FREYJA: {len(stations)} estaciones compatibles.\n"
                    f"ODIN: {reply.text}\n"
                )
            except (MarketSourceError, OpenAIError, OllamaError, RuntimeError) as error:
                self._ai_answer_state = {
                    "question": question, "answer": "", "error": str(error),
                    "model": "",
                }
            finally:
                self._ai_answer_busy.clear()

        threading.Thread(
            target=worker, name="odin-ai-written-station-search", daemon=True
        ).start()
        return True

    @staticmethod
    def _station_search_local_answer(stations) -> str:
        if not stations:
            return "FREYJA no encontró estaciones compatibles cercanas."
        parts = []
        for item in stations:
            pad = "plataforma grande" if item.get("large_pad") else "sin plataforma grande"
            parts.append(
                f"{item.get('station', 'estación')} en {item.get('system', 'sistema desconocido')}, "
                f"a {float(item.get('distance_ly', 0) or 0):.1f} años luz, {pad}"
            )
        return "FREYJA encontró: " + "; ".join(parts) + "."

    def request_powerplay_sale_search(
        self, commodity: str, allow_planetary: bool = True
    ) -> bool:
        """Inicia desde la GUI una búsqueda de venta para refuerzo Powerplay."""

        commodity = " ".join(str(commodity).split())
        if not commodity or self._trade_calculation_busy.is_set():
            return False
        self._start_freyja_powerplay_sale_search(commodity, allow_planetary)
        return True

    def refresh_canonn_poi(self, source: str) -> tuple[bool, str]:
        """Actualiza el catálogo sólo por una acción explícita del comandante."""

        normalized = str(source or "").strip()
        if not normalized:
            return False, localized_text(
                "canonn.source_required", self.config.language
            )
        try:
            items = self.canonn_poi_catalog.refresh(normalized)
        except CanonnPOIError as error:
            return False, str(error)
        return True, localized_text(
            "canonn.updated", self.config.language, count=len(items)
        )

    def _handle_powerplay_assignment_event(self, event: dict) -> None:
        event_name = str(event.get("event", ""))
        mission_id = str(event.get("MissionID", "") or "")
        if event_name == "MissionAccepted":
            self.powerplay_assignment_store.ingest_mission(event)
            return
        if not mission_id:
            return
        statuses = {
            "MissionCompleted": "completed",
            "MissionFailed": "failed",
            "MissionAbandoned": "abandoned",
        }
        status = statuses.get(event_name)
        if status:
            self.powerplay_assignment_store.set_status(
                mission_id, status,
                complete_progress=status == "completed",
            )

    def powerplay_weekly_guide(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Devuelve la guía estática; no captura ni interpreta la pantalla."""

        return tuple((key, tuple(steps)) for key, steps in SOLUTION_STEPS.items())

    def request_powerplay_activity(
        self, activity: str, subject: str = "", ai_question: str = ""
    ) -> tuple[bool, str]:
        selected = ACTIVITIES.get(str(activity).strip().casefold())
        if selected is None:
            return False, "Actividad Powerplay desconocida."
        if not self.commander_state.powerplay_power:
            return False, "No hay una potencia Powerplay afiliada en el Journal."
        if self._powerplay_activity.get("calculating"):
            return False, "Ya hay una búsqueda Powerplay en curso."
        subject = " ".join(str(subject).split())
        if selected.key in {"mining", "trade"} and not subject:
            noun = "mineral" if selected.key == "mining" else "mercancía"
            return False, f"Indicá la {noun} que querés buscar."
        self._powerplay_activity = {
            "key": selected.key,
            "start_merits": int(self.commander_state.powerplay_merits or 0),
            "calculating": True,
            "locations": [], "error": "", "subject": subject,
        }
        print(
            f"POWERPLAY: {selected.label} seleccionada. "
            f"Méritos iniciales: {self._powerplay_activity['start_merits']}."
        )
        position = self.commander_state.star_position
        if position is None:
            self._powerplay_activity["calculating"] = False
            self._powerplay_activity["error"] = "ODIN no conoce la posición actual."
            return False, self._powerplay_activity["error"]
        threading.Thread(
            target=self._search_powerplay_activity,
            args=(tuple(position), self.commander_state.powerplay_power,
                  selected.key, subject, ai_question),
            name=f"powerplay-{selected.key}-search", daemon=True,
        ).start()
        return True, selected.objective

    def _search_powerplay_activity(
        self, position: tuple[float, float, float], power: str, activity: str,
        subject: str, ai_question: str = "",
    ) -> None:
        try:
            locations = self._powerplay_search_client.activity_locations(
                position, power, activity
            )
            if activity == "mining":
                query = normalize_mineral_query(subject)
                hotspots = self._mining_search_client.locations(
                    self.commander_state.current_system, query,
                    max_distance_ly=900.0,
                )
                try:
                    if self.market_cache:
                        self.market_cache.refresh_region(
                            self._powerplay_market_client, position,
                            size=100, pages=3,
                        )
                except MarketSourceError as error:
                    self._powerplay_activity["source_warning"] = str(error)
                systems = [item.system for item in locations]
                requires_large_pad = bool(
                    getattr(self.trade_profile, "requires_large_pad", False)
                )
                sales = self.market_cache.sales_in_systems(
                    query, systems, requires_large_pad=requires_large_pad
                ) if self.market_cache else []
                plan = build_powerplay_mining_plan(locations, hotspots, sales)
                self._powerplay_activity["locations"] = plan
                if not hotspots:
                    self._powerplay_activity["error"] = (
                        f"No encontré hotspots comunitarios de {subject} dentro "
                        "de 900 años luz."
                    )
                elif not sales:
                    self._powerplay_activity["source_warning"] = (
                        f"Encontré dónde extraer {subject}, pero no una estación "
                        "Powerplay con mercado actualizado para entregarlo."
                    )
            elif activity == "trade":
                try:
                    if self.market_cache:
                        self.market_cache.refresh_region(
                            self._powerplay_market_client, position,
                            size=100, pages=3,
                        )
                except MarketSourceError as error:
                    self._powerplay_activity["source_warning"] = str(error)
                systems = [item.system for item in locations]
                requires_large_pad = bool(
                    getattr(self.trade_profile, "requires_large_pad", False)
                )
                sales = self.market_cache.sales_in_systems(
                    subject, systems, requires_large_pad=requires_large_pad
                ) if self.market_cache else []
                territory_by_system = {
                    item.system.casefold(): item for item in locations
                }
                matched = []
                for sale in sales:
                    territory = territory_by_system.get(
                        str(sale["system_name"]).casefold()
                    )
                    if territory is None:
                        continue
                    record = territory.to_dict()
                    record.update({
                        "station": sale["station_name"],
                        "sell_price": int(sale["sell_price"] or 0),
                        "demand": int(sale["demand"] or 0),
                        "has_large_pad": bool(sale["has_large_pad"]),
                        "market_updated_at": str(sale["updated_at"] or ""),
                    })
                    matched.append(record)
                self._powerplay_activity["locations"] = matched[:6]
                if not matched:
                    self._powerplay_activity["error"] = (
                        f"La caché no contiene mercados compatibles para {subject} "
                        "en los territorios candidatos."
                    )
            elif activity == "transport":
                try:
                    if self.market_cache:
                        self.market_cache.refresh_stations(
                            self._powerplay_market_client, position, pages=3
                        )
                except MarketSourceError as error:
                    self._powerplay_activity["source_warning"] = str(error)
                systems = [item.system for item in locations]
                requires_large_pad = bool(
                    getattr(self.trade_profile, "requires_large_pad", False)
                )
                stations = self.market_cache.stations_in_systems(
                    systems, requires_large_pad=requires_large_pad
                ) if self.market_cache else []
                territory_by_system = {
                    item.system.casefold(): item for item in locations
                }
                matched = []
                for station in stations:
                    territory = territory_by_system.get(
                        str(station["system_name"]).casefold()
                    )
                    if territory is None:
                        continue
                    record = territory.to_dict()
                    record.update({
                        "station": station["station_name"],
                        "has_large_pad": bool(station["has_large_pad"]),
                        "is_planetary": bool(station["is_planetary"]),
                        "distance_ls": float(station["distance_to_arrival"] or 0),
                        "station_type": str(station["station_type"] or ""),
                        "contact_unverified": True,
                    })
                    matched.append(record)
                self._powerplay_activity["locations"] = matched[:6]
                if not matched:
                    self._powerplay_activity["error"] = (
                        "La caché no contiene estaciones compatibles en los "
                        "territorios candidatos."
                    )
            elif activity in {"exploration", "on_foot", "salvage"}:
                systems = [item.system for item in locations]
                requires_large_pad = bool(
                    getattr(self.trade_profile, "requires_large_pad", False)
                ) if activity != "on_foot" else False
                stations = self.market_cache.stations_in_systems(
                    systems, requires_large_pad=requires_large_pad, limit=400,
                ) if self.market_cache else []
                matched = match_station_locations(locations, stations, activity)
                self._powerplay_activity["locations"] = matched[:6]
                if not matched:
                    labels = {
                        "exploration": "Universal Cartographics",
                        "on_foot": "asentamientos Odyssey",
                        "salvage": "Search and Rescue",
                    }
                    self._powerplay_activity["error"] = (
                        f"La caché no contiene {labels[activity]} dentro de los "
                        "territorios candidatos. Actualizá estaciones desde una "
                        "búsqueda autorizada antes de repetir."
                    )
            else:
                self._powerplay_activity["locations"] = [
                    item.to_dict() for item in locations[:6]
                ]
            if not locations:
                self._powerplay_activity["error"] = (
                    "No se encontraron territorios comunitarios compatibles."
                )
        except (PowerplaySearchError, MiningSearchError, ValueError) as error:
            self._powerplay_activity["error"] = str(error)
        finally:
            self._powerplay_activity["calculating"] = False
            if ai_question:
                report = dict(self._powerplay_activity)
                if (not self.config.public_beta_no_ai
                        and (self.config.ai_provider == "ollama"
                        or self.config.ai_share_powerplay_data)):
                    self._officer_ai_results.put((ai_question, "POWERPLAY", report))
                else:
                    local_answer = str(report.get("error", "") or "").strip()
                    if not local_answer:
                        locations = report.get("locations", []) or []
                        if locations:
                            first = locations[0]
                            local_answer = (
                                "Encontré una opción Powerplay en "
                                f"{first.get('system', 'un sistema cercano')}."
                            )
                        else:
                            local_answer = "No encontré ubicaciones Powerplay compatibles."
                    self._officer_ai_results.put((
                        ai_question, "POWERPLAY", {"local_answer": local_answer}
                    ))

    def powerplay_location_to_heimdall(self, system: str) -> bool:
        """Entrega un candidato Powerplay al planificador sin trazarlo solo."""

        normalized = " ".join(str(system).split())
        if not normalized:
            return False
        self.dashboard_snapshot.setdefault("powerplay", {})["selected_system"] = normalized
        return True

    def _start_freyja_powerplay_sale_search(
        self, commodity: str, allow_planetary: bool = True
    ) -> None:
        if self._trade_calculation_busy.is_set():
            self._start_fixed_voice_response(
                self._t("freyja.voice.busy"),
                officer="FREYJA",
            )
            return
        self._trade_calculation_busy.set()
        self._trade_requested_strategy = "powerplay"
        self._trade_requested_commodity = commodity
        self._powerplay_sale_result = {
            "active": False,
            "strategy": "Venta Powerplay",
            "commodity": commodity,
            "target": "—",
            "units": 0,
            "estimated_profit": 0,
            "progress": "Consultando mercados Powerplay",
            "unit_price": 0,
            "distance_ly": 0.0,
            "powerplay_state": "Consultando",
        }
        self._voice_busy.set()
        print(
            f"FREYJA: {self._t('freyja.voice.powerplay_search', commodity=commodity)}\n"
        )
        threading.Thread(
            target=self._run_freyja_powerplay_sale_search,
            args=(commodity, allow_planetary),
            name="freyja-powerplay-sale-search",
            daemon=True,
        ).start()

    def _run_freyja_powerplay_sale_search(
        self, commodity: str, allow_planetary: bool = True
    ) -> None:
        try:
            if self.navigation_manager is None:
                answer = self._t("freyja.voice.no_ship_position")
            else:
                profile = TradeProfileBuilder.build(
                    self.commander_state,
                    self.navigation_manager.context,
                    self.config.cargo_file,
                )
                if not profile.powerplay_power:
                    answer = self._t("freyja.voice.no_power")
                elif profile.position is None:
                    answer = self._t("freyja.voice.no_coordinates")
                else:
                    destination = PowerplaySaleFinder().find(
                        commodity,
                        profile.powerplay_power,
                        profile.position,
                        requires_large_pad=profile.requires_large_pad,
                        allow_planetary=allow_planetary,
                    )
                    if destination is None:
                        self._powerplay_sale_result.update({
                            "progress": "Sin mercado Powerplay disponible",
                            "powerplay_state": profile.powerplay_power,
                        })
                        answer = self._t(
                            "freyja.voice.no_powerplay_market",
                            power=profile.powerplay_power, commodity=commodity,
                        )
                    else:
                        copy_text(destination.system)
                        units = min(profile.cargo_used, destination.demand)
                        self._powerplay_sale_result.update({
                            "active": True,
                            "strategy": "Venta Powerplay",
                            "commodity": commodity,
                            "target": f"{destination.station} Â· {destination.system}",
                            "units": units,
                            "estimated_profit": 0,
                            "progress": "Destino de venta calculado (sin méritos confirmados)",
                            "unit_price": destination.sell_price,
                            "distance_ly": destination.distance_ly,
                            "powerplay_state": (
                                f"{destination.power_state} Â· {destination.power}"
                            ),
                        })
                        answer = self._t(
                            "freyja.voice.powerplay_result",
                            station=destination.station, system=destination.system,
                            state=destination.power_state, power=destination.power,
                            distance=f"{destination.distance_ly:.0f}",
                            price=destination.sell_price,
                        )
            self._start_fixed_voice_response(answer, officer="FREYJA")
        except MarketSourceError:
            self._powerplay_sale_result.update({
                "progress": "Error al consultar mercados comunitarios",
                "powerplay_state": "Sin datos",
            })
            self._start_fixed_voice_response(
                self._t("freyja.voice.community_error"),
                officer="FREYJA",
            )
        finally:
            self._trade_calculation_busy.clear()

    def _announce_freyja_trade_start(self, selection: str) -> None:
        announcements = {
            "quick": self._t("freyja.voice.quick"),
            "three_station": self._t("freyja.voice.three"),
            "expedition": self._t("freyja.voice.expedition"),
            "powerplay": self._t("freyja.voice.powerplay"),
        }
        announcement = announcements.get(
            selection,
            self._t("freyja.voice.selected"),
        )
        print(f"FREYJA: {announcement}\n")
        try:
            OfficerVoiceService(self.config).speak("FREYJA", announcement)
        except VoiceServiceError as error:
            print(f"Voz de FREYJA no disponible: {error}\n")
        finally:
            # La búsqueda de mercados puede tardar varios segundos. Una vez que
            # FREYJA confirmó la modalidad, ODIN debe volver a escuchar sin
            # esperar a que termine la consulta de red.
            self._voice_busy.clear()
            self.wake_listener.resume()

    def _calculate_freyja_trade(
        self, selection: str, market_cache: MarketCache,
        preferred_commodity: str = "",
        allow_planetary: bool = True,
    ) -> None:
        if blocker := self.active_trade_route.recalculation_blocker():
            self._start_fixed_voice_response(blocker, officer="FREYJA")
            return
        if self.navigation_manager is None:
            self._start_fixed_voice_response(
                self._t("freyja.voice.no_navigation"),
                officer="FREYJA",
            )
            return
        self.trade_profile = TradeProfileBuilder.build(
            self.commander_state,
            self.navigation_manager.context,
            self.config.cargo_file,
        )
        self.trade_profile = replace(
            self.trade_profile, allow_planetary=bool(allow_planetary)
        )
        profile_blocker = self._freyja_trade_profile_blocker(
            self.trade_profile, self.config.language
        )
        if profile_blocker is not None:
            self._start_fixed_voice_response(profile_blocker, officer="FREYJA")
            return
        planning_notice = ""
        calculation_profile = self.trade_profile
        if self.trade_profile.cargo_free <= 0:
            calculation_profile = replace(self.trade_profile, cargo_used=0)
            planning_notice = self._t(
                "freyja.voice.release_cargo", cargo=self.trade_profile.cargo_used
            )
        planning_profile = self._freyja_planning_profile(
            selection, calculation_profile
        )
        self._freyja_used_stale_cache = False
        if selection in {"quick", "three_station", "expedition"}:
            # Cada solicitud comienza con datos comunitarios actuales. SQLite
            # conserva esos datos y solo actúa como respaldo si falla Spansh.
            plan = self._refresh_and_recalculate_freyja(
                selection, planning_profile, market_cache, preferred_commodity
            )
        else:
            if not self.trade_profile.powerplay_power:
                self._start_fixed_voice_response(
                    self._t("freyja.voice.no_power_profile"),
                    officer="FREYJA",
                )
                return
            center = self.POWERPLAY_TRADE_CENTERS.get(
                self.trade_profile.powerplay_power.casefold(),
                self.BUBBLE_TRADE_CENTER,
            )
            try:
                recent_count = market_cache.refresh_region(
                    SpanshMarketClient(), center, size=100, pages=5,
                    sort_by="market_updated_at",
                )
                nearby_count = market_cache.refresh_region(
                    SpanshMarketClient(), center, size=100, pages=5,
                    sort_by="distance",
                )
                self._freyja_market_refresh_count = recent_count + nearby_count
                max_age_hours = self.FREYJA_POWERPLAY_MAX_AGE_HOURS
            except MarketSourceError:
                self._freyja_used_stale_cache = True
                max_age_hours = self.FREYJA_POWERPLAY_MAX_AGE_HOURS
            opportunities = market_cache.opportunities(
                planning_profile, sell_power=self.trade_profile.powerplay_power,
            )
            opportunities = self._filter_trade_commodity(
                opportunities, preferred_commodity
            )
            plan = PowerplayTradeOptimizer().choose(
                planning_profile, opportunities,
                max_age_hours=max_age_hours,
            )
        if plan is None:
            if self._freyja_used_stale_cache:
                message = self._t("freyja.voice.no_cached_operation")
            else:
                message = self._t(
                    "freyja.voice.no_filtered_market",
                    count=self._freyja_market_refresh_count,
                )
            self._start_fixed_voice_response(message, officer="FREYJA")
            return
        if selection == "quick":
            answer = self._quick_trade_voice_summary(plan, self.config.language)
        else:
            answer = plan.summary(self.config.language)
        self.active_trade_route.activate(plan, selection)
        if self._freyja_used_stale_cache:
            answer = self._t("freyja.voice.stale_cache") + answer
        if (not self.config.public_beta_no_ai and (
                self.config.ai_provider == "ollama" or self.config.ai_share_trade_data)):
            self._officer_ai_results.put((
                "Explicá al comandante la operación comercial calculada por FREYJA, "
                "incluyendo producto, estaciones, toneladas, beneficio, compatibilidad "
                "de plataforma y cualquier advertencia disponible.",
                "FREYJA",
                {
                    "strategy": selection,
                    "officer_summary": planning_notice + answer,
                    "trade": self._dashboard_trade(),
                    "market_refresh_count": self._freyja_market_refresh_count,
                    "used_stale_cache": self._freyja_used_stale_cache,
                },
            ))
        else:
            self._start_fixed_voice_response(
                planning_notice + answer, officer="FREYJA"
            )

    @staticmethod
    def _freyja_trade_profile_blocker(profile, language: str = "es-419") -> str | None:
        if profile.cargo_capacity <= 0:
            return localized_text("freyja.voice.no_cargo_capacity", language)
        if profile.available_capital <= 0:
            return localized_text("freyja.voice.no_capital", language)
        if profile.jump_range <= 0:
            return localized_text("freyja.voice.no_jump_range", language)
        return None

    def _freyja_planning_profile(self, selection: str, profile=None):
        """Separa el viaje a la Burbuja del presupuesto de la expedici\u00f3n."""
        profile = profile or self.trade_profile
        if profile.position is None:
            return profile
        distance_to_bubble = math.dist(profile.position, self.BUBBLE_TRADE_CENTER)
        if distance_to_bubble <= 500:
            return profile
        return replace(
            profile,
            system="Lembava",
            position=self.BUBBLE_TRADE_CENTER,
        )

    def _refresh_and_recalculate_freyja(
        self, selection: str, profile, market_cache: MarketCache,
        preferred_commodity: str = "",
    ):
        try:
            market_cache.refresh_region(
                SpanshMarketClient(), self.BUBBLE_TRADE_CENTER,
                size=100 if selection == "three_station" else 75,
                pages=3 if selection == "three_station" else 1,
            )
        except MarketSourceError:
            self._freyja_used_stale_cache = True
            max_age_hours = self.FREYJA_CACHE_FALLBACK_MAX_AGE_HOURS
        else:
            max_age_hours = self.FREYJA_MARKET_MAX_AGE_HOURS
        opportunities = market_cache.opportunities(profile)
        opportunities = self._filter_trade_commodity(
            opportunities, preferred_commodity
        )
        if selection == "quick":
            return QuickRouteOptimizer().choose(
                profile, opportunities,
                max_age_hours=max_age_hours,
            )
        if selection == "three_station":
            return ThreeStationOptimizer().choose(
                profile, opportunities,
                max_age_hours=max_age_hours,
            )
        return TradeExpeditionOptimizer().choose(
            profile, opportunities, max_jumps=30,
            max_age_hours=max_age_hours,
        )

    @staticmethod
    def _filter_trade_commodity(opportunities, preferred_commodity: str):
        preferred = " ".join(str(preferred_commodity).casefold().split())
        if not preferred:
            return opportunities
        return [
            opportunity for opportunity in opportunities
            if preferred in opportunity.commodity.casefold()
        ]

    @staticmethod
    def _quick_trade_voice_summary(plan, language: str = "es-419") -> str:
        item = plan.opportunity
        return localized_text(
            "freyja.voice.quick_summary", language, units=plan.units,
            commodity=item.commodity, buy_station=item.buy_station,
            buy_system=item.buy_system, sell_station=item.sell_station,
            sell_system=item.sell_system, profit=plan.estimated_profit,
            jumps=item.jumps,
        ) + (
            localized_text("freyja.voice.stale_price", language)
            if plan.stale_hours > 24 else ""
        )

    def _start_officer_voice_message(self, message: VoiceMessageReady) -> None:
        self._voice_busy.set()
        self.wake_listener.pause()
        threading.Thread(
            target=self._run_officer_voice_message,
            args=(message,),
            name=f"{message.officer.lower()}-voice-message",
            daemon=True,
        ).start()

    def _run_officer_voice_message(self, message: VoiceMessageReady) -> None:
        try:
            print(f"{message.officer}: {message.message}\n")
            OfficerVoiceService(self.config).speak(message.officer, message.message)
        except VoiceServiceError as error:
            print(f"Voz de {message.officer} no disponible: {error}\n")
        finally:
            self._voice_busy.clear()
            self.wake_listener.resume()

    def _handle_heimdall_navigation_event(self, event: dict) -> None:
        if self.navigation_manager is None:
            return
        self.navigation_manager.handle_event(event)
        self._announce_high_energy_guidance(event)
        if event.get("event") == "FSDJump":
            route_systems = tuple(
                waypoint.system
                for waypoint in self.navigation_manager.context.route
            )
            route_update = self.heimdall_route_planner.advance_if_arrived(
                event.get("StarSystem", ""),
                route_systems,
            )
            if route_update is not None:
                self.heimdall_diagnostics.record_route_clipboard_update(
                    route_update
                )
                self.console_presenter.show_route_progress(route_update)
                if (
                    route_update.route_abandoned
                    and route_update.destination_system
                    and self.config.heimdall_auto_replan_enabled
                ):
                    self._start_automatic_replan(route_update.destination_system)
        if event.get("event") in {"FSDJump", "FSDTarget", "JetConeBoost"}:
            self.heimdall_diagnostics.record_navigation_context(
                self.navigation_manager.context,
                reason=event.get("event", "evento"),
            )

    def _announce_high_energy_guidance(self, event: dict) -> None:
        event_name = str(event.get("event", ""))
        guidance = self.navigation_manager.context.high_energy_guidance(event_name)
        if guidance.stage == "idle":
            return
        marker = (
            guidance.stage,
            str(event.get("Name") or event.get("StarSystem") or ""),
            (
                self.navigation_manager.context.cone_exposures_session
                if guidance.stage == "charged"
                else int(event.get("BoostUsed") or 0)
            ),
        )
        if marker in self._heimdall_cone_announcements:
            return
        self._heimdall_cone_announcements.add(marker)
        if guidance.stage == "approach":
            key = (
                "heimdall.cone.white_dwarf"
                if guidance.star_type == "white_dwarf"
                else "heimdall.cone.neutron"
            )
        elif guidance.stage == "charged":
            key = "heimdall.cone.charged"
        else:
            key = "heimdall.cone.complete"
        message = self._t(key)
        if guidance.fsd_health is not None:
            message += self._t(
                "heimdall.cone.health", health=guidance.fsd_health * 100
            )
        self._officer_voice_messages.put(
            VoiceMessageReady("HEIMDALL", message, "guía segura de sobrecarga FSD")
        )

    def plan_heimdall_route(self, destination: str, *, efficiency: int = 60):
        """Punto de entrada para una futura orden de voz de navegación."""

        if self.navigation_manager is None:
            raise RuntimeError("El contexto de HEIMDALL no fue inicializado.")
        plan = self.heimdall_route_planner.plan_fastest(
            self.navigation_manager.context,
            destination,
            efficiency=efficiency,
        )
        self.heimdall_diagnostics.record_planned_route(plan)
        return plan

    def _start_automatic_replan(self, destination: str) -> None:
        if self.navigation_manager is None or self._route_replan_busy.is_set():
            return
        context = self.navigation_manager.context
        snapshot = NavigationContext(
            current_system=context.current_system,
            max_jump_range=context.max_jump_range,
        )
        self._route_replan_busy.set()
        threading.Thread(
            target=self._calculate_automatic_replan,
            args=(snapshot, destination),
            name="heimdall-automatic-replan",
            daemon=True,
        ).start()

    def _calculate_automatic_replan(
        self, context: NavigationContext, destination: str
    ) -> None:
        try:
            plan = self.heimdall_route_planner.calculate_fastest(
                context, destination
            )
            self._automatic_route_results.put((plan, None, destination))
        except (SpanshRouteError, ValueError) as error:
            self.heimdall_diagnostics.record_route_error(destination, error)
            self._automatic_route_results.put((None, "route_error", destination))

    def _finish_automatic_replan(
        self, plan, error: str | None, destination: str
    ) -> None:
        self._route_replan_busy.clear()
        if error is not None:
            message = self._t("heimdall.voice.replan_error")
        else:
            try:
                self.heimdall_route_planner.activate(plan)
                self.heimdall_diagnostics.record_planned_route(plan)
                next_system = (
                    plan.next_waypoint.system if plan.next_waypoint else None
                )
                message = self._t(
                    "heimdall.voice.replanned", destination=plan.destination_system,
                    jumps=plan.actual_total_jumps,
                )
                if next_system:
                    message += self._t("heimdall.voice.replanned_copied", system=next_system)
            except (OSError, RuntimeError, ValueError) as route_error:
                self.heimdall_diagnostics.record_route_error(
                    destination, route_error
                )
                message = self._t("heimdall.voice.replan_activation_error")
        self._officer_voice_messages.put(
            VoiceMessageReady("HEIMDALL", message, "replanificación de ruta")
        )

    @staticmethod
    def _show_header() -> None:
        """
        Muestra el encabezado inicial de ODIN.
        """

        print("=" * 50)
        print(f"ODIN v{VERSION} - {CAPABILITY}")
        print("Orbital Data Intelligence Nexus")
        print("=" * 50)
