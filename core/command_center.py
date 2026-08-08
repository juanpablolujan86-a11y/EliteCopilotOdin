"""
ODIN - Orbital Data Intelligence Nexus

command_center.py

Inicializa, conecta y coordina los componentes principales de ODIN.
"""

import time
import threading
import queue
import re
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
from mimir.context_registry import ScientificContextRegistry
from models.events.voice_message_ready import VoiceMessageReady
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
from heimdall.cockpit import CockpitAdvisor, parse_cockpit_intent
from heimdall.home_base import HomeBaseManager
from heimdall.navigation import NavigationContext, NavigationContextManager
from heimdall.spansh import HeimdallRoutePlanner, SpanshClient, SpanshRouteError
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
        self.cockpit_advisor = CockpitAdvisor()
        self.navigation_manager: NavigationContextManager | None = None
        self.heimdall_diagnostics = HeimdallDiagnostics(self.config.data_root)
        self.home_base_manager = HomeBaseManager(self.config.data_root)
        self.heimdall_route_planner = HeimdallRoutePlanner(
            self.database,
            SpanshClient(),
        )
        self.exploration_processor: ExplorationProcessor | None = None
        self.expedition_ledger: ExpeditionLedger | None = None
        self.voice_hotkey = WindowsHotkey()
        self._voice_busy = threading.Event()
        self._voice_questions: queue.Queue[str] = queue.Queue()
        self._route_results: queue.Queue[tuple[object | None, str | None]] = queue.Queue()
        self._officer_voice_messages: queue.Queue[VoiceMessageReady] = queue.Queue()
        self._surface_ready_announced: set[tuple[int, int]] = set()
        self.scientific_context = ScientificContextRegistry()
        self.command_memory = VoiceCommandMemory(self.database)
        self._last_voice_question = ""
        self._last_learned_command: LearnedCommand | None = None
        self._restoring_context = False
        self.wake_listener = WakeWordListener(
            self.config.data_root, self._voice_questions.put
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

        self._initialize_heimdall()

        self._initialize_heimdall_navigation(journal)

        self._initialize_home_base()

        self._restore_commander_state(journal)

        self._configure_processors()

        self._rebuild_current_system(journal)

        self.watcher = JournalWatcher(journal)
        self.watcher.start()

        print(f"\nJournal: {journal.name}")
        print("\nODIN está observando Elite Dangerous...")
        print("Esperando eventos.\n")
        print("Conversación          : presioná F8 para hablar con ODIN\n")
        print("Activación por voz     : decí ODIN y formulá tu consulta\n")
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
            "SetUserShipName", "ShipyardSwap", "ShipyardBuy",
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

        while True:
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

            if self.voice_hotkey.pressed() and not self._voice_busy.is_set():
                print("\nODIN escucha. Hablá y terminá con un segundo de silencio...")
                self.wake_listener.arm()

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

            if not self._voice_busy.is_set():
                try:
                    officer_message = self._officer_voice_messages.get_nowait()
                except queue.Empty:
                    officer_message = None
                if officer_message is not None:
                    self._start_officer_voice_message(officer_message)

            events = self.watcher.poll()

            for event in events:
                self.event_bus.publish(event)

            time.sleep(0.1)

    def _start_voice_response(self, question: str) -> None:
        """Responde en segundo plano sin detener el seguimiento del Journal."""
        commander = self.commander_state.fid or self.commander_state.commander_name or "default"
        lowered = question.casefold().strip()
        previous_question = self._last_voice_question

        cockpit_intent = parse_cockpit_intent(question)
        if cockpit_intent is not None:
            answer = self.cockpit_advisor.describe(cockpit_intent)
            self.heimdall_diagnostics.record_cockpit_advice(
                cockpit_intent, self.cockpit_advisor.state, answer
            )
            self._last_voice_question = question
            self._last_learned_command = None
            self._start_fixed_voice_response(answer)
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
                    "No tengo una base registrada para el comandante."
                )
            else:
                self._start_voice_route(base.system)
            return
        if learned is not None and learned.intent == "neutron_route":
            self._start_voice_route(learned.payload["destination"])
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
        if parse_home_route_intent(text) is not None:
            return LearnedCommand("home_route", {})
        route = parse_neutron_route_intent(text)
        if route is not None:
            return LearnedCommand("neutron_route", {"destination": route.destination})
        return None

    def _run_voice_response(self, question: str, context: str) -> None:
        try:
            answer = VoiceConversation(self.config).respond(question, context)
            print(f"\nVos: {question}")
            print(f"ODIN: {answer}\n")
        except (MicrophoneError, TranscriptionError, OllamaError, VoiceServiceError) as error:
            print(f"\nConversación por voz no disponible: {error}\n")
        finally:
            self._voice_busy.clear()
            self.wake_listener.resume()

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
            self._start_fixed_voice_response(
                "HEIMDALL todavía no tiene disponible el contexto de navegación."
            )
            return
        context = self.navigation_manager.context
        snapshot = NavigationContext(
            current_system=context.current_system,
            max_jump_range=context.max_jump_range,
        )
        self._voice_busy.set()
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
        if error is not None:
            self._start_fixed_voice_response(
                "No pude calcular la ruta de neutrones. Se produjo un error."
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
        self._start_fixed_voice_response(answer)

    def _start_fixed_voice_response(self, answer: str) -> None:
        self._voice_busy.set()
        threading.Thread(
            target=self._run_fixed_voice_response,
            args=(answer,),
            name="odin-fixed-voice-response",
            daemon=True,
        ).start()

    def _run_fixed_voice_response(self, answer: str) -> None:
        try:
            print(f"ODIN: {answer}\n")
            OfficerVoiceService(self.config).speak("ODIN", answer)
        except VoiceServiceError as error:
            print(f"Voz no disponible: {error}\n")
        finally:
            self._voice_busy.clear()
            self.wake_listener.resume()

    def _start_officer_voice_message(self, message: VoiceMessageReady) -> None:
        self._voice_busy.set()
        self.wake_listener.paused.set()
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
