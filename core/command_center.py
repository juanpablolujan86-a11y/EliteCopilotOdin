"""
ODIN - Orbital Data Intelligence Nexus

command_center.py

Inicializa, conecta y coordina los componentes principales de ODIN.
"""

import time

from brain.decision_engine import DecisionEngine
from core.config import Config
from core.database import DatabaseManager
from core.event_bus import EventBus
from core.journal_reader import JournalReader
from core.journal_watcher import JournalWatcher
from core.processors import commander_state_updater
from core.processors.edsm_lookup import EDSMLookup
from core.processors.jump_advisor import JumpAdvisor
from core.processors.jump_processor import JumpProcessor
from core.processors.jump_store import JumpStore
from core.processors.system_memory import SystemMemory
from services.edsm_service import EDSMService
from core.processors.exploration_context_builder import (
    ExplorationContextBuilder,
)
from core.processors.commander_state_updater import CommanderStateUpdater
from state.commander_state import CommanderState
from core.internal_events import InternalEvent
from ui.console_presenter import ConsolePresenter

class CommandCenter:
    """
    Centro de mando principal de ODIN.

    Se encarga de:
    - Inicializar los componentes.
    - Conectar los procesadores al EventBus.
    - Escuchar el Journal de Elite Dangerous.
    - Cerrar correctamente los recursos.
    """

    def __init__(self) -> None:
        self.config = Config()

        self.database = DatabaseManager(
            self.config.project_root
        )

        self.event_bus = EventBus()
        self.edsm_service = EDSMService()
        self.decision_engine = DecisionEngine()
        self.commander_state = CommanderState()
        self.commander_state_updater = CommanderStateUpdater(self.commander_state)
        self.console_presenter = ConsolePresenter()

        self.watcher: JournalWatcher | None = None

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

        self._configure_processors()

        self.watcher = JournalWatcher(journal)
        self.watcher.start()

        print(f"\nJournal: {journal.name}")
        print("\nODIN está observando Elite Dangerous...")
        print("Esperando eventos.\n")

        try:
            self._run_event_loop()

        except KeyboardInterrupt:
            print("\nODIN detenido por el comandante.")

        finally:
            self.database.disconnect()
            print("Base de datos desconectada correctamente.")

    def _find_active_journal(self):
        """
        Busca el Journal más recientemente modificado.
        """

        reader = JournalReader(
            self.config.journal_path
        )

        return reader.latest_file()

    def _configure_processors(self) -> None:
        """
        Crea y registra los procesadores de eventos.
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

        context_builder = ExplorationContextBuilder(
    self.database
)

        jump_advisor = JumpAdvisor(
    context_builder,
    self.decision_engine,
    self.event_bus
)

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
            self.commander_state_updater.handle_fsd_jump
        )

        self.event_bus.subscribe(
            "FSDJump",
            jump_advisor.handle
        )
        self.event_bus.subscribe(
    InternalEvent.RECOMMENDATION_READY,
    self.console_presenter.show_recommendation
)
    def _run_event_loop(self) -> None:
        """
        Mantiene a ODIN escuchando eventos nuevos.
        """

        if self.watcher is None:
            raise RuntimeError(
                "JournalWatcher no fue inicializado."
            )

        while True:
            events = self.watcher.poll()

            for event in events:
                self.event_bus.publish(event)

            time.sleep(0.1)

    @staticmethod
    def _show_header() -> None:
        """
        Muestra el encabezado inicial de ODIN.
        """

        print("=" * 50)
        print("ODIN v0.3 - Bifröst")
        print("Orbital Data Intelligence Nexus")
        print("=" * 50)