import sys

from core.command_center import CommandCenter
from core.config import Config
from core.diagnostics import configure_diagnostics, log_fatal_error
from core.single_instance import SingleInstance
from intelligence.assistant import OdinLocalAssistant
from intelligence.ollama import OllamaError
from voice.configurator import run_voice_configuration
from voice.key_file import import_key_file


def main() -> None:
    config = Config()
    key_import = import_key_file()
    if key_import.message:
        print(key_import.message)

    if "--configure-voice" in sys.argv:
        run_voice_configuration(config)
        return

    if "--test-ai" in sys.argv:
        index = sys.argv.index("--test-ai")
        question = " ".join(sys.argv[index + 1:]).strip()
        if not question:
            question = "Presentate brevemente y confirmá que funcionás de forma local."
        try:
            print(OdinLocalAssistant().ask(question).text)
        except (OllamaError, ValueError) as error:
            print(f"IA local no disponible: {error}")
        return

    instance = SingleInstance()

    if not instance.acquire():
        print("\nODIN ya está ejecutándose. No se abrirá una segunda copia.")
        return

    try:
        configure_diagnostics(config.data_root)
        odin = CommandCenter()
        odin.start()
    except Exception:
        log_fatal_error()
        print(
            "\nODIN encontró un error inesperado. "
            f"Revisá el registro en: {config.data_root / 'logs' / 'odin.log'}"
        )
        input("Presioná Enter para cerrar...")
    finally:
        instance.close()


if __name__ == "__main__":
    main()
