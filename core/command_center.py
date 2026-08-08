"""
ODIN - Orbital Data Intelligence Nexus

command_center.py

Inicializa, conecta y coordina los componentes principales de ODIN.
"""

import time
import threading
from contextlib import redirect_stdout
from io import StringIO

from brain.decision_engine import DecisionEngine
from core.config import Config
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
from core.processors.jump_advisor import JumpAdvisor
from core.processors.jump_processor import JumpProcessor
from core.processors.jump_store import JumpStore
from core.processors.system_memory import SystemMemory
from services.edsm_service import EDSMService
from state.commander_state import CommanderState
from ui.console_presenter import ConsolePresenter
from core.version import CAPABILITY, VERSION
from core.diagnostics import HeimdallDiagnostics, MimirDiagnostics, OdinDiagnostics
from heimdall.bindings import BindingAudit, BindingCustodian
from heimdall.navigation import NavigationContextManager
from heimdall.spansh import HeimdallRoutePlanner, SpanshClient
from intelligence.context import build_live_context
from intelligence.ollama import OllamaError
from speech.conversation import VoiceConversation
from speech.hotkey import WindowsHotkey
from speech.recorder import MicrophoneError
from speech.whisper import TranscriptionError
from voice.service import VoiceServiceError

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
        self.status_watcher = StatusWatcher(self.config.status_file)
        self.surface_navigation = SurfaceNavigationTracker()
        self.binding_custodian = BindingCustodian(
            self.config.bindings_path,
            self.config.data_root,
        )
        self.binding_audit: BindingAudit | None = None
        self.navigation_manager: NavigationContextManager | None = None
        self.heimdall_diagnostics = HeimdallDiagnostics(self.config.data_root)
        self.heimdall_route_planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(),
        )
        self.exploration_processor: ExplorationProcessor | None = None
        self.expedition_ledger: ExpeditionLedger | None = None
        self.voice_hotkey = WindowsHotkey()
        self._voice_busy = threading.Event()

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

        self._initialize_heimdall()

        self._initialize_heimdall_navigation(journal)

        self._restore_commander_state(journal)

        self._configure_processors()

        self._rebuild_current_system(journal)

        self.watcher = JournalWatcher(journal)
        self.watcher.start()

        print(f"\nJournal: {journal.name}")
        print("\nODIN está observando Elite Dangerous...")
        print("Esperando eventos.\n")
        print("Conversación          : presioná F8 para hablar con ODIN\n")

        try:
            self._run_event_loop()

        except KeyboardInterrupt:
            print("\nODIN detenido por el comandante.")

        finally:
            self.database.disconnect()
            print("Base de datos desconectada correctamente.")

    def _initialize_heimdall(self) -> None:
        """Audita y respalda bindings sin modificar los originales."""

        self.binding_audit = self.binding_custodian.audit(create_snapshot=True)
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

        CommanderStateUpdater(self.commander_state).restore_context(context)
        print(
            "Estado restaurado     : "
            f"Sistema actual {self.commander_state.current_system}"
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

        expedition_ledger = ExpeditionLedger(
            self.database,
            self.event_bus,
            self.config.project_root / "knowledge" / "biology" / "species.json",
        )
        expedition_ledger.bootstrap()
        self.expedition_ledger = expedition_ledger
        self.exploration_processor = exploration_processor

        mimir_diagnostics = MimirDiagnostics(self.config.data_root)
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

        self.event_bus.subscribe(
            "MultiSellExplorationData",
            expedition_ledger.handle_exploration_sale,
        )

        self.event_bus.subscribe(
            "SellOrganicData",
            expedition_ledger.handle_organic_sale,
        )

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

        # Se registra para el futuro sintetizador; deliberadamente no se
        # presenta en pantalla.
        self.event_bus.subscribe(
            InternalEvent.VOICE_MESSAGE_READY,
            mimir_diagnostics.record_voice_message,
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
        try:
            with redirect_stdout(silent_output):
                for event in events:
                    handler = handlers.get(event.get("event"))
                    if handler is None:
                        continue
                    handler(event)
                    restored += 1
        finally:
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

        while True:
            status = self.status_watcher.poll()
            if status is not None:
                if self.navigation_manager is not None:
                    self.navigation_manager.update_status(status)
                navigation = self.surface_navigation.update_status(status)
                if navigation is not None:
                    self.event_bus.publish_internal(
                        InternalEvent.SURFACE_NAVIGATION_UPDATED,
                        navigation,
                    )

            if self.navigation_manager is not None:
                self.navigation_manager.poll_route()

            if self.voice_hotkey.pressed() and not self._voice_busy.is_set():
                self._start_voice_conversation()

            events = self.watcher.poll()

            for event in events:
                self.event_bus.publish(event)

            time.sleep(0.1)

    def _start_voice_conversation(self) -> None:
        """Escucha en segundo plano sin detener el seguimiento del Journal."""

        balance = (
            self.expedition_ledger.summary("consulta por voz")
            if self.expedition_ledger is not None else None
        )
        navigation = (
            self.navigation_manager.context
            if self.navigation_manager is not None else None
        )
        context = build_live_context(self.commander_state, navigation, balance)
        self._voice_busy.set()
        print("\nODIN escucha durante 7 segundos. Hablá ahora...")
        threading.Thread(
            target=self._run_voice_conversation,
            args=(context,),
            name="odin-voice-conversation",
            daemon=True,
        ).start()

    def _run_voice_conversation(self, context: str) -> None:
        try:
            question, answer = VoiceConversation(self.config).listen_once(7, context)
            print(f"\nVos: {question}")
            print(f"ODIN: {answer}\n")
        except (MicrophoneError, TranscriptionError, OllamaError, VoiceServiceError) as error:
            print(f"\nConversación por voz no disponible: {error}\n")
        finally:
            self._voice_busy.clear()

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

    @staticmethod
    def _show_header() -> None:
        """
        Muestra el encabezado inicial de ODIN.
        """

        print("=" * 50)
        print(f"ODIN v{VERSION} - {CAPABILITY}")
        print("Orbital Data Intelligence Nexus")
        print("=" * 50)
