import time

from core.config import Config
from core.database import DatabaseManager
from core.event_bus import EventBus
from core.journal_reader import JournalReader
from core.journal_watcher import JournalWatcher
from core.processors.edsm_lookup import EDSMLookup
from core.processors.jump_processor import JumpProcessor
from core.processors.jump_store import JumpStore
from core.processors.system_memory import SystemMemory
from services.edsm_service import EDSMService


def main():
    print("=" * 50)
    print("ODIN v0.3 - Bifröst")
    print("Orbital Data Intelligence Nexus")
    print("=" * 50)

    config = Config()
    reader = JournalReader(config.journal_path)
    journal = reader.latest_file()

    if journal is None:
        print("\nNo se encontró ningún Journal.")
        return

    database = DatabaseManager(config.project_root)
    database.connect()
    database.create_tables()

    event_bus = EventBus()

    edsm_service = EDSMService()

    jump_processor = JumpProcessor()
    jump_store = JumpStore(database)
    system_memory = SystemMemory(database)
    edsm_lookup = EDSMLookup(edsm_service)

    event_bus.subscribe("FSDJump", jump_processor.handle)
    event_bus.subscribe("FSDJump", jump_store.handle)
    event_bus.subscribe("FSDJump", system_memory.handle)
    event_bus.subscribe("FSDJump", edsm_lookup.handle)

    watcher = JournalWatcher(journal)
    watcher.start()

    print(f"\nJournal: {journal.name}")
    print("\nODIN está observando Elite Dangerous...")
    print("Esperando un salto FSD.\n")

    try:
        while True:
            events = watcher.poll()

            for event in events:
                event_bus.publish(event)

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nODIN detenido por el comandante.")

    finally:
        database.disconnect()
        print("Base de datos desconectada correctamente.")


if __name__ == "__main__":
    main()