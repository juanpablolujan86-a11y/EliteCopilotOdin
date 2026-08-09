"""
ODIN - Orbital Data Intelligence Nexus

command_center.py

Inicializa, conecta y coordina los componentes principales de ODIN.
"""

import time
import threading
import queue
import re
import math
from dataclasses import replace
from contextlib import redirect_stdout
from io import StringIO

from brain.decision_engine import DecisionEngine
from core.config import Config
from core.body_names import planet_reference
from core.database import DatabaseManager
from core.event_bus import EventBus
from core.expedition_ledger import ExpeditionLedger
from core.internal_events import InternalEvent
from core.journal_reader import JournalReader
from core.journal_watcher import JournalWatcher
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
from heimdall.bindings import BindingAudit, BindingCustodian
from heimdall.cockpit import CockpitAdvisor, parse_cockpit_intent
from heimdall.home_base import HomeBaseManager
from heimdall.navigation import NavigationContext, NavigationContextManager
from heimdall.spansh import HeimdallRoutePlanner, SpanshClient, SpanshRouteError
from heimdall.synthesis import FSDInjectionInventory
from intelligence.context import build_live_context
from intelligence.command_memory import LearnedCommand, VoiceCommandMemory
from intelligence.intents import parse_home_route_intent, parse_neutron_route_intent
from intelligence.ollama import OllamaError
from speech.conversation import VoiceConversation
from speech.hotkey import WindowsHotkey
from speech.wake_word import WakeWordListener
from speech.recorder import MicrophoneError
from speech.whisper import TranscriptionError
from voice.service import OfficerVoiceService, VoiceServiceError

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
    POWERPLAY_TRADE_CENTERS = {
        "li yong-rui": (-43.25, -64.34375, -77.6875),
    }
    BUBBLE_TRADE_CENTER = (-43.25, -64.34375, -77.6875)
    FREYJA_MARKET_MAX_AGE_HOURS = 168.0
    FREYJA_CACHE_FALLBACK_MAX_AGE_HOURS = 720.0

    def __init__(self) -> None:
        self.config = Config()

        self.database = DatabaseManager(
            self.config.data_root
        )

        self.event_bus = EventBus()
        self.edsm_service = EDSMService()
        self.decision_engine = DecisionEngine()

        self.commander_state = CommanderState()
        self.console_presenter = ConsolePresenter()

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
        self.cockpit_advisor = CockpitAdvisor()
        self.fsd_injections = FSDInjectionInventory(
            self.config.data_root / "heimdall" / "fsd_materials.json"
        )
        self.navigation_manager: NavigationContextManager | None = None
        self.heimdall_diagnostics = HeimdallDiagnostics(self.config.data_root)
        self.home_base_manager = HomeBaseManager(self.config.data_root)
        self.heimdall_route_planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(),
        )
        self.exploration_processor: ExplorationProcessor | None = None
        self.expedition_ledger: ExpeditionLedger | None = None
        self.trade_profile = None
        self.market_cache: MarketCache | None = None
        self._pending_freyja_trade_menu = False
        self._pending_freyja_cancel_confirmation = False
        self.voice_hotkey = WindowsHotkey()
        self._voice_busy = threading.Event()
        self._voice_questions: queue.Queue[str] = queue.Queue()
        self._wake_activations: queue.Queue[bool] = queue.Queue()
        self._unclear_voice_commands: queue.Queue[bool] = queue.Queue()
        self._wake_acknowledgement_index = 0
        self._wake_acknowledgement_lock = threading.Lock()
        self._route_acknowledgement_done = threading.Event()
        self._route_acknowledgement_done.set()
        self._route_results: queue.Queue[tuple[object | None, str | None]] = queue.Queue()
        self._manual_route_requests: queue.Queue[str] = queue.Queue()
        self._route_calculation_busy = threading.Event()
        self._automatic_route_results: queue.Queue[
            tuple[object | None, str | None, str]
        ] = queue.Queue()
        self._route_replan_busy = threading.Event()
        self._officer_voice_messages: queue.Queue[VoiceMessageReady] = queue.Queue()
        self._surface_ready_announced: set[tuple[int, int]] = set()
        self.scientific_context = ScientificContextRegistry()
        self.command_memory = VoiceCommandMemory(self.database)
        self._last_voice_question = ""
        self._last_learned_command: LearnedCommand | None = None
        self._restoring_context = False
        self._stop_requested = threading.Event()
        self.dashboard_snapshot: dict = {"status": "Inicializando"}
        self._last_dashboard_refresh = 0.0
        self.wake_listener = WakeWordListener(
            self.config.data_root,
            self._voice_questions.put,
            lambda: self._wake_activations.put(True),
            lambda: self._unclear_voice_commands.put(True),
        )

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
        )

        scientific_officer = ScientificOfficer(
            species_file=self.config.project_root / "knowledge" / "biology" / "species.json",
            rules_file=self.config.project_root / "knowledge" / "biology" / "prediction_rules.json",
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
        ):
            self.event_bus.subscribe(event_name, commander_state_updater.handle_profile_event)
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
        freyja_ledger = TradeLedger(self.database, freyja_diagnostics)
        self.freyja_ledger = freyja_ledger
        self.active_trade_route = ActiveTradeRoute(
            self.config.data_root / "freyja" / "active_route.json",
            self.event_bus,
            diagnostics=freyja_diagnostics,
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
            exploration_processor.handle_saa_signals_found
        )

        self.event_bus.subscribe(
            "FSSBodySignals",
            exploration_processor.handle_saa_signals_found
        )

        self.event_bus.subscribe(
            "ScanOrganic",
            exploration_processor.handle_scan_organic
        )

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
                self.cockpit_advisor.update_status(status)
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
                        next_ordinal = (
                            "segunda" if navigation.progress == 1 else "tercera"
                        )
                        self.event_bus.publish_internal(
                            InternalEvent.VOICE_MESSAGE_READY,
                            VoiceMessageReady(
                                officer="MÍMIR",
                                message=(
                                    "Comandante, ya te alejaste la distancia "
                                    f"necesaria. Podés recolectar la {next_ordinal} "
                                    "muestra."
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
                    self._start_wake_acknowledgement()

            if not self._voice_busy.is_set():
                try:
                    unclear_command = self._unclear_voice_commands.get_nowait()
                except queue.Empty:
                    unclear_command = False
                if unclear_command:
                    self.wake_listener.arm()
                    self._start_fixed_voice_response(
                        "No entendí la orden. Repítala, comandante."
                    )

            if not self._voice_busy.is_set():
                try:
                    question = self._voice_questions.get_nowait()
                except queue.Empty:
                    question = ""
                if question:
                    self._start_voice_response(question)

            try:
                route_plan, route_error = self._route_results.get_nowait()
            except queue.Empty:
                route_plan, route_error = None, None
            if route_plan is not None or route_error is not None:
                self._finish_voice_route(route_plan, route_error)

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

            events = self.watcher.poll()

            for event in events:
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

    def request_stop(self) -> None:
        """Solicita un cierre ordenado desde la interfaz gráfica."""

        self._stop_requested.set()

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
        biology = self._dashboard_biology(predictions)
        try:
            route = self.heimdall_route_planner.active_route_snapshot()
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
            "route": route,
            "route_calculating": (
                self._route_calculation_busy.is_set()
                or not self._manual_route_requests.empty()
            ),
            "biology": biology,
            "injections": {
                "basic": injections.basic,
                "standard": injections.standard,
                "premium": injections.premium,
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

    def _dashboard_biology(
        self, predictions: dict[str, tuple[str, ...]]
    ) -> dict:
        """Combina señales reales persistidas con predicciones de MÍMIR."""

        bodies: dict[tuple[int | None, str], dict] = {}
        if self.commander_state.system_address:
            rows = self.database.query(
                """
                SELECT body_id, body_name, source_event, signal_type,
                       signal_count, genus, species
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
                body_name = row["body_name"] or known_names.get(body_id) or f"Cuerpo {body_id}"
                key = (body_id, body_name)
                item = bodies.setdefault(key, {
                    "body": body_name, "signals": 0,
                    "confirmed": set(), "probable": set(),
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
        by_name = {item["body"].casefold(): item for item in bodies.values()}
        for body_name, species in predictions.items():
            item = by_name.get(body_name.casefold())
            if item is None:
                item = {
                    "body": body_name, "signals": 0,
                    "confirmed": set(), "probable": set(),
                }
                bodies[(None, body_name)] = item
                by_name[body_name.casefold()] = item
            item["probable"].update(species)
        details = tuple({
            "body": item["body"],
            "signals": item["signals"],
            "confirmed": tuple(sorted(item["confirmed"])),
            "probable": tuple(sorted(item["probable"])),
        } for item in bodies.values() if item["signals"] or item["confirmed"] or item["probable"])
        return {
            "bodies": len(details),
            "species": sum(max(item["signals"], len(item["confirmed"]), len(item["probable"])) for item in details),
            "predictions": predictions,
            "details": details,
        }

    def _start_wake_acknowledgement(self) -> None:
        self._voice_busy.set()
        threading.Thread(
            target=self._run_wake_acknowledgement,
            name="odin-wake-acknowledgement",
            daemon=True,
        ).start()

    def _prepare_wake_acknowledgement(self) -> None:
        try:
            warm_up = getattr(self.wake_listener.transcriber, "warm_up", None)
            if callable(warm_up):
                ready = warm_up()
                print(
                    "Reconocimiento de voz: "
                    + ("Faster Whisper Small listo" if ready else "whisper.cpp de respaldo")
                )
            voice = OfficerVoiceService(self.config)
            messages = tuple(
                ("ODIN", message) for message in self.WAKE_ACKNOWLEDGEMENTS
            ) + (
                ("ODIN", "Revisando la base de datos."),
                ("ODIN", "Consultando los registros científicos."),
                ("ODIN", "Revisando los datos del comandante."),
                ("ODIN", "Procesando la orden, comandante."),
                ("HEIMDALL", "Calculando la ruta, comandante."),
                (
                    "FREYJA",
                    "Opción uno seleccionada: ruta rápida. Comienzo a buscar la operación con mayor ganancia por minuto, comandante.",
                ),
                (
                    "FREYJA",
                    "Opción dos seleccionada: circuito de tres estaciones. Comienzo a calcular el circuito comercial, comandante.",
                ),
                (
                    "FREYJA",
                    "Opción tres seleccionada: expedición comercial. Comienzo a buscar una ruta de hasta treinta saltos, comandante.",
                ),
                (
                    "FREYJA",
                    "Opción cuatro seleccionada: comercio Powerplay. Comienzo a buscar una operación compatible con su potencia, comandante.",
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
            print("ODIN escucha. Hablá y terminá con un segundo de silencio...")
        except VoiceServiceError as error:
            print(f"Voz de ODIN no disponible: {error}\n")
        finally:
            self._voice_busy.clear()
            self.wake_listener.resume()

    def _next_wake_acknowledgement(self) -> str:
        with self._wake_acknowledgement_lock:
            acknowledgement = self.WAKE_ACKNOWLEDGEMENTS[
                self._wake_acknowledgement_index
            ]
            self._wake_acknowledgement_index = (
                self._wake_acknowledgement_index + 1
            ) % len(self.WAKE_ACKNOWLEDGEMENTS)
            return acknowledgement

    def _start_voice_response(self, question: str) -> None:
        """Responde en segundo plano sin detener el seguimiento del Journal."""
        if getattr(self, "_pending_freyja_cancel_confirmation", False):
            if self._is_freyja_trade_cancel_confirmation(question):
                self._pending_freyja_cancel_confirmation = False
                self.active_trade_route.cancel()
                self._start_fixed_voice_response(
                    "Cancelación comercial confirmada. Dejé de seguir la ruta.",
                    officer="FREYJA",
                )
            else:
                self._start_fixed_voice_response(
                    "La ruta continúa activa. Para cancelarla diga: confirmo "
                    "la cancelación comercial.",
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
                "No reconoc\u00ed la modalidad. Eleg\u00ed uno: ruta r\u00e1pida; dos: circuito de tres estaciones; tres: expedici\u00f3n de hasta treinta saltos; o cuatro: comercio Powerplay.",
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
            self.wake_listener.arm()
            self._start_fixed_voice_response(
                "No entendí la orden. Repítala, comandante."
            )
            return
        commander = self.commander_state.fid or self.commander_state.commander_name or "default"
        lowered = question.casefold().strip()
        previous_question = self._last_voice_question

        if self._is_freyja_trade_request(question):
            self.command_memory.remember(
                commander, question, "freyja_trade_menu", {}
            )
            self._open_freyja_trade_menu()
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
                self._freyja_ledger_voice_summary(self.freyja_ledger.summary()),
                officer="FREYJA",
            )
            return

        if self._is_freyja_trade_recalculate_request(question):
            strategy = self.active_trade_route.active_strategy()
            if strategy is None:
                self._start_fixed_voice_response(
                    "No hay una ruta comercial activa para recalcular.",
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
                    blocker + " Diga: confirmo la cancelación comercial.",
                    officer="FREYJA",
                    arm_after=True,
                )
                return
            cancelled = self.active_trade_route.cancel()
            self._start_fixed_voice_response(
                (
                    "Ruta comercial cancelada, comandante."
                    if cancelled else
                    "No hay una ruta comercial activa para cancelar."
                ),
                officer="FREYJA",
            )
            return

        cockpit_intent = parse_cockpit_intent(question)
        if cockpit_intent is not None:
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
                answer = "Todavía no tengo disponible el contexto de navegación."
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
        if any(text in lowered for text in ("eso esta bien", "eso está bien", "orden correcta")):
            confirmed = bool(previous_question) and self.command_memory.confirm(
                commander, previous_question
            )
            self._start_fixed_voice_response(
                "Entendido. Voy a recordar esa forma de hablar."
                if confirmed else "Todavía no tengo una orden anterior para confirmar."
            )
            return
        if any(text in lowered for text in ("olvida esa orden", "olvidá esa orden", "olvidate de esa orden")):
            forgotten = bool(previous_question) and self.command_memory.forget(
                commander, previous_question
            )
            self._last_learned_command = None
            self._start_fixed_voice_response(
                "Olvidé esa asociación."
                if forgotten else "No encontré una orden aprendida para olvidar."
            )
            return

        correction = re.search(r"\b(?:quise|queria|quería)\s+decir\s+(.+)$", question, re.IGNORECASE)
        if correction and previous_question:
            corrected = correction.group(1).strip()
            learned = self._command_from_text(corrected)
            if learned is not None:
                self.command_memory.remember(
                    commander, previous_question, learned.intent, learned.payload
                )
                self._last_learned_command = learned
                self._start_fixed_voice_response(
                    "Entendido. Guardé la corrección para la próxima vez."
                )
            else:
                self._start_fixed_voice_response(
                    "Entendí la corrección, pero todavía no puedo asociarla a una acción segura."
                )
            return

        learned = self.command_memory.resolve(commander, question)
        if learned is None:
            learned = self._command_from_text(question)
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
                    "No tengo una base registrada para el comandante.",
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
        context = build_live_context(
            self.commander_state,
            navigation,
            balance,
            biology,
            self.home_base_manager.current.system
            if self.home_base_manager.current is not None else "",
        )
        self._voice_busy.set()
        threading.Thread(
            target=self._run_voice_response,
            args=(question, context),
            name="odin-voice-conversation",
            daemon=True,
        ).start()

    @staticmethod
    def _command_from_text(text: str) -> LearnedCommand | None:
        if CommandCenter._is_freyja_trade_request(text):
            return LearnedCommand("freyja_trade_menu", {})
        if parse_home_route_intent(text) is not None:
            return LearnedCommand("home_route", {})
        route = parse_neutron_route_intent(text)
        if route is not None:
            return LearnedCommand("neutron_route", {"destination": route.destination})
        return None

    @staticmethod
    def _is_fsd_injection_status_request(text: str) -> bool:
        lowered = text.casefold()
        mentions_injection = (
            "inyeccion" in lowered or "inyección" in lowered
        ) and any(
            term in lowered for term in ("fsd", "salto", "sintesis", "síntesis")
        )
        mentions_jump_synthesis = (
            "material" in lowered
            and ("sintesis" in lowered or "síntesis" in lowered)
            and ("fsd" in lowered or "salto" in lowered)
        )
        return mentions_injection or mentions_jump_synthesis

    @staticmethod
    def _fsd_injection_distance_request(text: str) -> float | None:
        lowered = text.casefold()
        if not any(term in lowered for term in (
            "inyeccion", "inyección", "saltar", "salto", "alcanzar",
        )):
            return None
        match = re.search(
            r"(\d+(?:[\.,]\d+)?)\s*(?:años?\s+luz|anos?\s+luz|ly)\b",
            lowered,
        )
        if match is None:
            return None
        return float(match.group(1).replace(",", "."))

    @staticmethod
    def _is_route_injection_status_request(text: str) -> bool:
        lowered = text.casefold()
        return "ruta" in lowered and (
            "inyeccion" in lowered
            or "inyección" in lowered
            or ("sintesis" in lowered or "síntesis" in lowered)
        )

    @staticmethod
    def _is_fsd_injection_authorization(text: str) -> bool:
        lowered = text.casefold()
        return bool(re.search(
            r"\b(?:autorizo|confirmo|apruebo)\b.*\b(?:inyeccion|inyección)\b.*\bfsd\b",
            lowered,
        ))

    def _open_freyja_trade_menu(self) -> None:
        self._pending_freyja_trade_menu = True
        self._start_fixed_voice_response(
            "Tengo cuatro modelos disponibles para usted, comandante. Uno: ruta r\u00e1pida, para maximizar ganancias por minuto. Dos: circuito de tres estaciones, comerciando tres productos diferentes. Tres: expedici\u00f3n comercial de hasta treinta saltos, para maximizar el ingreso total. Cuatro: comercio Powerplay, para buscar cr\u00e9ditos y m\u00e9ritos de su potencia. Indique el n\u00famero o el nombre de la modalidad.",
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
        }
        return words[0] in accepted_short_orders

    def _run_voice_response(self, question: str, context: str) -> None:
        acknowledgement_done = threading.Event()
        threading.Thread(
            target=self._run_processing_message,
            args=(
                "ODIN",
                self._processing_message_for(question),
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
            conversation.voice.speak("ODIN", answer)
            print(f"\nVos: {question}")
            print(f"ODIN: {answer}\n")
        except (MicrophoneError, TranscriptionError, OllamaError, VoiceServiceError) as error:
            print(f"\nConversación por voz no disponible: {error}\n")
        finally:
            acknowledgement_done.wait()
            self._voice_busy.clear()
            self.wake_listener.resume()

    @staticmethod
    def _processing_message_for(question: str) -> str:
        lowered = question.casefold()
        if any(word in lowered for word in ("biolog", "especie", "muestra", "mímir", "mimir")):
            return "Consultando los registros científicos."
        if any(word in lowered for word in ("crédito", "credito", "nave", "combustible", "comandante")):
            return "Revisando los datos del comandante."
        if any(word in lowered for word in ("sistema", "planeta", "base de datos", "escane")):
            return "Revisando la base de datos."
        return "Procesando la orden, comandante."

    def _sanitize_current_system_references(self, question: str, answer: str) -> str:
        """Evita repetir por voz el nombre completo de la ubicación actual."""

        lowered = question.casefold()
        asks_for_name = (
            ("sistema" in lowered and any(term in lowered for term in (
                "cómo se llama", "como se llama", "cuál es", "cual es",
                "en qué", "en que", "dónde estoy", "donde estoy",
            )))
            or "sistema actual" in lowered
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
            "este sistema",
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
                "Todavía no tengo disponible el contexto de navegación.",
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
                "Calculando la ruta, comandante.",
                self._route_acknowledgement_done,
            ),
            name="heimdall-processing-message",
            daemon=True,
        ).start()
        print(
            f"\nHEIMDALL calcula una ruta de neutrones desde "
            f"{snapshot.current_system or 'origen desconocido'} hasta {destination}..."
        )
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
                "No pude calcular la ruta de neutrones. Se produjo un error.",
                officer="HEIMDALL",
                wait_for=self._route_acknowledgement_done,
            )
            return
        try:
            self.heimdall_route_planner.activate(plan)
            self.heimdall_diagnostics.record_planned_route(plan)
            next_system = plan.next_waypoint.system if plan.next_waypoint else None
            answer = (
                f"Ruta de neutrones calculada desde {plan.source_system} hasta "
                f"{plan.destination_system}: {plan.actual_total_jumps} saltos y "
                f"{plan.distance:.0f} años luz. "
            )
            conventional = plan.conventional_minimum_jumps
            saved = plan.estimated_jumps_saved
            if conventional is not None and saved is not None:
                if saved > 0:
                    answer += (
                        f"La referencia convencional mínima sería de {conventional} "
                        f"saltos; esta ruta ahorra al menos {saved}. "
                    )
                else:
                    answer += (
                        "Esta autopista no mejora la referencia convencional mínima; "
                        "conviene comparar también la ruta trazada por el juego. "
                    )
            if next_system:
                answer += f"Copié {next_system} al portapapeles como primer destino."
            else:
                answer += "Ya te encontrás en el destino."
        except (OSError, RuntimeError, ValueError) as route_error:
            self.heimdall_diagnostics.record_route_error(
                getattr(plan, "destination_system", "desconocido"),
                route_error,
            )
            answer = "La ruta fue calculada, pero se produjo un error al activarla."
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
        lowered = text.casefold()
        normalized = re.sub(r"[^a-z0-9\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1]+", " ", lowered).strip()
        normalized = re.sub(r"\bgase+r\b", "hacer", normalized)
        explicit_trade = "comerci" in normalized and any(
            word in normalized
            for word in ("freyja", "freya", "quiero", "hacer", "vamos", "deseo")
        )
        buy_and_sell = (
            re.search(r"\bcompr(?:ar|o|amos)?\b", normalized)
            and re.search(r"\bvend(?:er|o|emos)?\b", normalized)
        )
        # Confusi\u00f3n ac\u00fastica real observada con Whisper Base al decir
        # "quiero comerciar". S\u00f3lo se interpreta dentro de una orden activada.
        observed_whisper_alias = bool(
            re.search(r"\b(?:el\s+)?fin\s+de\s+la\s+proxima\s+vez\b", normalized)
            or re.search(r"\b(?:el\s+)?fin\s+de\s+la\s+pr\u00f3xima\s+vez\b", normalized)
            or normalized in {"vale bien", "y vale bien"}
        )
        return bool(explicit_trade or buy_and_sell or observed_whisper_alias)

    @staticmethod
    def _is_eddn_status_request(text: str) -> bool:
        lowered = text.casefold()
        return "eddn" in lowered and bool(re.search(
            r"\b(?:estado|funciona|activo|activa|transmisi[oó]n|env[ií]os?|datos)\b",
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
        summary: EDDNOutboxSummary, capture_enabled: bool, upload_enabled: bool
    ) -> str:
        if not capture_enabled:
            return "La captura de datos para EDDN está desactivada."
        if not upload_enabled:
            return (
                "La captura de EDDN está activa, pero la transmisión está desactivada. "
                f"Hay {summary.pending} mensajes pendientes."
            )
        last = (
            f" El último tipo enviado fue {summary.last_sent_event}."
            if summary.last_sent_event else
            " Todavía no se enviaron eventos desde esta cola."
        )
        return (
            "La transmisión a EDDN está activa. "
            f"Hay {summary.sent} enviados, {summary.pending} pendientes, "
            f"{summary.retrying} en reintento y {summary.rejected} rechazados."
            + last
        )

    @staticmethod
    def _is_freyja_trade_status_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(r"\b(?:estado|progreso)\b.*\bruta\s+comercial\b", lowered)
            or re.search(r"\bqu[eé]\s+(?:tengo\s+que\s+)?(?:comprar|vender)\b", lowered)
            or "siguiente tramo" in lowered
            or bool(re.search(r"\brepet(?:i|í|ir)\b.*\b(?:instrucci[oó]n|tramo)\b", lowered))
            or bool(re.search(
                r"\b(?:beneficio|ganancia)\b.*\bruta\b|\bruta\b.*\b(?:beneficio|ganancia)\b",
                lowered,
            ))
            or "tramos quedan" in lowered
        )

    @staticmethod
    def _is_freyja_trade_ledger_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:beneficio|ganancia|invert[ií]|ventas?|vendido)\b",
                lowered,
            )
            and re.search(r"\b(?:comercio|comercial|comerciando|llevo)\b", lowered)
        )

    @staticmethod
    def _freyja_ledger_voice_summary(summary: TradeSummary) -> str:
        return (
            f"Balance comercial confirmado: invertimos {summary.invested} créditos, "
            f"vendimos por {summary.revenue} créditos y la ganancia realizada es "
            f"de {summary.realized_profit} créditos. Hay {summary.cargo_units} "
            "toneladas registradas en el inventario comercial."
        )

    @staticmethod
    def _is_freyja_trade_cancel_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:cancela|cancelá|cancelar|abandona|abandoná)\b"
                r".*\bruta\s+comercial\b",
                lowered,
            )
        )

    @staticmethod
    def _is_freyja_trade_cancel_confirmation(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\bconfirmo\b.*\bcancelaci[oó]n\s+comercial\b",
                lowered,
            )
        )

    @staticmethod
    def _is_freyja_trade_recalculate_request(text: str) -> bool:
        lowered = text.casefold()
        return bool(
            re.search(
                r"\b(?:recalcula|recalculá|recalcular|actualiza|actualizá)\b"
                r".*\bruta\s+comercial\b",
                lowered,
            )
        )

    @staticmethod
    def _freyja_trade_selection(text: str) -> str | None:
        lowered = text.casefold()
        if re.search(r"\b(?:1|uno|primera|rapida|r\u00e1pida)\b", lowered):
            return "quick"
        if re.search(r"\b(?:2|dos|segunda|tres estaciones|circuito)\b", lowered):
            return "three_station"
        if re.search(r"\b(?:3|tres|tercera|treinta saltos|expedicion|expedici\u00f3n)\b", lowered):
            return "expedition"
        if re.search(r"\b(?:4|cuatro|cuarta|powerplay|meritos|m\u00e9ritos)\b", lowered):
            return "powerplay"
        return None

    def _start_freyja_trade_calculation(self, selection: str) -> None:
        self._voice_busy.set()
        print("FREYJA: Consultando mercados de la Burbuja...\n")
        threading.Thread(
            target=self._run_freyja_trade_calculation,
            args=(selection,),
            name=f"freyja-{selection}-calculation",
            daemon=True,
        ).start()

    def _run_freyja_trade_calculation(self, selection: str) -> None:
        trade_database = DatabaseManager(self.config.data_root)
        try:
            self._announce_freyja_trade_start(selection)
            trade_database.connect()
            trade_database.create_tables()
            self._calculate_freyja_trade(selection, MarketCache(trade_database))
        except Exception:
            self._start_fixed_voice_response(
                "Se produjo un error al calcular la operaci\u00f3n comercial. Int\u00e9ntelo nuevamente, comandante.",
                officer="FREYJA",
            )
        finally:
            trade_database.disconnect()

    def _announce_freyja_trade_start(self, selection: str) -> None:
        announcements = {
            "quick": (
                "Opción uno seleccionada: ruta rápida. "
                "Comienzo a buscar la operación con mayor ganancia por minuto, comandante."
            ),
            "three_station": (
                "Opción dos seleccionada: circuito de tres estaciones. "
                "Comienzo a calcular el circuito comercial, comandante."
            ),
            "expedition": (
                "Opción tres seleccionada: expedición comercial. "
                "Comienzo a buscar una ruta de hasta treinta saltos, comandante."
            ),
            "powerplay": (
                "Opción cuatro seleccionada: comercio Powerplay. "
                "Comienzo a buscar una operación compatible con su potencia, comandante."
            ),
        }
        announcement = announcements.get(
            selection,
            "Modalidad seleccionada. Comienzo el cálculo comercial, comandante.",
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

    def _calculate_freyja_trade(self, selection: str, market_cache: MarketCache) -> None:
        if blocker := self.active_trade_route.recalculation_blocker():
            self._start_fixed_voice_response(blocker, officer="FREYJA")
            return
        if self.navigation_manager is None:
            self._start_fixed_voice_response(
                "El planificador comercial todav\u00eda no tiene disponible el estado de navegaci\u00f3n.",
                officer="FREYJA",
            )
            return
        self.trade_profile = TradeProfileBuilder.build(
            self.commander_state,
            self.navigation_manager.context,
            self.config.cargo_file,
        )
        profile_blocker = self._freyja_trade_profile_blocker(self.trade_profile)
        if profile_blocker is not None:
            self._start_fixed_voice_response(profile_blocker, officer="FREYJA")
            return
        planning_notice = ""
        calculation_profile = self.trade_profile
        if self.trade_profile.cargo_free <= 0:
            calculation_profile = replace(self.trade_profile, cargo_used=0)
            planning_notice = (
                "Planificación anticipada: antes de comprar deberá liberar "
                f"{self.trade_profile.cargo_used} toneladas de carga. "
            )
        planning_profile = self._freyja_planning_profile(
            selection, calculation_profile
        )
        self._freyja_used_stale_cache = False
        opportunities = (
            [] if selection == "powerplay"
            else market_cache.opportunities(planning_profile)
        )
        if selection == "quick":
            plan = QuickRouteOptimizer().choose(
                planning_profile, opportunities,
                max_age_hours=self.FREYJA_MARKET_MAX_AGE_HOURS,
            )
            if plan is None:
                plan = self._refresh_and_recalculate_freyja(
                    selection, planning_profile, market_cache
                )
        elif selection == "three_station":
            plan = ThreeStationOptimizer().choose(
                planning_profile, opportunities,
                max_age_hours=self.FREYJA_MARKET_MAX_AGE_HOURS,
            )
            if plan is None:
                plan = self._refresh_and_recalculate_freyja(
                    selection, planning_profile, market_cache
                )
        elif selection == "expedition":
            plan = TradeExpeditionOptimizer().choose(
                planning_profile, opportunities, max_jumps=30
                , max_age_hours=self.FREYJA_MARKET_MAX_AGE_HOURS
            )
            if plan is None:
                try:
                    market_cache.refresh_region(
                        SpanshMarketClient(), self.BUBBLE_TRADE_CENTER, size=75
                    )
                    opportunities = market_cache.opportunities(planning_profile)
                    plan = TradeExpeditionOptimizer().choose(
                        planning_profile, opportunities, max_jumps=30
                        , max_age_hours=self.FREYJA_MARKET_MAX_AGE_HOURS
                    )
                except MarketSourceError:
                    self._start_fixed_voice_response(
                        "No pude actualizar los mercados comunitarios en este momento. Int\u00e9ntelo nuevamente m\u00e1s tarde.",
                        officer="FREYJA",
                    )
                    return
        else:
            if not self.trade_profile.powerplay_power:
                self._start_fixed_voice_response(
                    "No encuentro una potencia Powerplay afiliada en los datos del comandante.",
                    officer="FREYJA",
                )
                return
            opportunities = market_cache.opportunities(
                planning_profile,
                sell_power=self.trade_profile.powerplay_power,
            )
            plan = PowerplayTradeOptimizer().choose(
                planning_profile, opportunities,
                max_age_hours=self.FREYJA_MARKET_MAX_AGE_HOURS,
            )
            if plan is None:
                center = self.POWERPLAY_TRADE_CENTERS.get(
                    self.trade_profile.powerplay_power.casefold()
                )
                if center is not None:
                    try:
                        market_cache.refresh_region(
                            SpanshMarketClient(), center, size=75
                        )
                        opportunities = market_cache.opportunities(
                            planning_profile,
                            sell_power=self.trade_profile.powerplay_power,
                        )
                        plan = PowerplayTradeOptimizer().choose(
                            planning_profile, opportunities,
                            max_age_hours=self.FREYJA_MARKET_MAX_AGE_HOURS,
                        )
                    except MarketSourceError:
                        self._start_fixed_voice_response(
                            "No pude actualizar los mercados comunitarios en este momento. Int\u00e9ntelo nuevamente m\u00e1s tarde.",
                            officer="FREYJA",
                        )
                        return
        if plan is None:
            self._start_fixed_voice_response(
                "No encontr\u00e9 una operaci\u00f3n factible con los mercados actualizados disponibles. Necesito recibir m\u00e1s datos de mercado dentro de la Burbuja.",
                officer="FREYJA",
            )
            return
        if selection == "quick":
            answer = self._quick_trade_voice_summary(plan)
        else:
            answer = plan.summary()
        self.active_trade_route.activate(plan, selection)
        if self._freyja_used_stale_cache:
            answer = (
                "El mercado comunitario no respondió; calculé con la última "
                "caché disponible. Confirme los precios antes de comprar. "
                + answer
            )
        self._start_fixed_voice_response(
            planning_notice + answer, officer="FREYJA"
        )

    @staticmethod
    def _freyja_trade_profile_blocker(profile) -> str | None:
        if profile.cargo_capacity <= 0:
            return (
                "No puedo iniciar una operación comercial porque la nave no "
                "tiene capacidad de carga disponible."
            )
        if profile.available_capital <= 0:
            return (
                "No puedo iniciar una operación comercial sin créditos disponibles "
                "por encima de la reserva de seguridad."
            )
        if profile.jump_range <= 0:
            return (
                "No puedo calcular la operación porque todavía no conozco el "
                "alcance de salto de la nave."
            )
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
        self, selection: str, profile, market_cache: MarketCache
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
    def _quick_trade_voice_summary(plan) -> str:
        item = plan.opportunity
        return (
            f"Compre {plan.units} toneladas de {item.commodity} en "
            f"{item.buy_station}, sistema {item.buy_system}, y v\u00e9ndalas en "
            f"{item.sell_station}, sistema {item.sell_system}. La ganancia "
            f"estimada es de {plan.estimated_profit} cr\u00e9ditos en "
            f"{item.jumps} saltos."
            + (
                " Confirme el precio al llegar; uno de los mercados tiene m\u00e1s de un d\u00eda."
                if plan.stale_hours > 24 else ""
            )
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
            message = (
                "Detecté el desvío, pero no pude recalcular la ruta en este "
                "momento. El detalle quedó registrado."
            )
        else:
            try:
                self.heimdall_route_planner.activate(plan)
                self.heimdall_diagnostics.record_planned_route(plan)
                next_system = (
                    plan.next_waypoint.system if plan.next_waypoint else None
                )
                message = (
                    f"Ruta recalculada hacia {plan.destination_system}: "
                    f"{plan.actual_total_jumps} saltos."
                )
                if next_system:
                    message += f" Copié {next_system} al portapapeles."
            except (OSError, RuntimeError, ValueError) as route_error:
                self.heimdall_diagnostics.record_route_error(
                    destination, route_error
                )
                message = (
                    "Calculé la nueva ruta, pero no pude activarla. El detalle "
                    "quedó registrado."
                )
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
