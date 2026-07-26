from core.config import Config
from core.journal_reader import JournalReader


def main():

    print("=" * 50)
    print("ODIN v0.1")
    print("Orbital Data Intelligence Nexus")
    print("=" * 50)

    config = Config()

    reader = JournalReader(config.journal_path)

    journal = reader.latest_file()

    if journal is None:
        print("\nNo se encontró ningún Journal.")
        return

    print("\n✔ Journal encontrado")
    print(journal.name)

    print("\nÚltimo evento registrado:")

    event = reader.last_event()

    print(event.get("event", "Desconocido"))

    print("\nODIN listo.\n")


if __name__ == "__main__":
    main()