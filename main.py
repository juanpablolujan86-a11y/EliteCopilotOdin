import sys

from core.command_center import CommandCenter
from core.config import Config
from core.diagnostics import configure_diagnostics, log_fatal_error
from platform_adapters.single_instance import create_single_instance
from intelligence.assistant import OdinLocalAssistant
from intelligence.ollama import OllamaError
from intelligence.openai_client import OpenAIClient, OpenAIError
from intelligence.ollama_runtime import ensure_ollama_server
from speech.conversation import VoiceConversation
from speech.recorder import MicrophoneError
from speech.whisper import TranscriptionError
from voice.configurator import run_voice_configuration
from voice.key_file import import_key_file
from voice.key_file import application_directory
from services.edsm_key_file import import_edsm_key_file
from services.inara_key_file import import_inara_key_file
from voice.service import OfficerVoiceService, VoiceServiceError
from voice.settings import VoiceSettingsRepository, apply_language_voice_preset
from ui.desktop import run_desktop
from installer.ollama_gui import run_ollama_setup
from installer.local_speech_gui import run_local_speech_setup


def configure_language(config: Config, language: str) -> str:
    """Persiste el idioma público y aplica las voces Edge correspondientes."""

    config.update_preferences(language=language)
    settings_repository = VoiceSettingsRepository(config.data_root)
    settings = settings_repository.load()
    apply_language_voice_preset(settings, config.language)
    settings_repository.save(settings)
    return config.language


def main() -> None:
    if "--install-ollama" in sys.argv:
        raise SystemExit(run_ollama_setup())
    if "--install-local-speech" in sys.argv:
        raise SystemExit(run_local_speech_setup())

    standalone_modes = {
        "--configure-voice", "--test-ai", "--test-openai", "--test-voice",
        "--ask-odin", "--talk", "--set-language",
        "--install-local-speech",
    }
    instance = None
    if not any(mode in sys.argv for mode in standalone_modes):
        # La exclusión debe ocurrir antes de tocar Ollama: un segundo acceso
        # directo no puede iniciar otro servidor ni mostrar otra consola.
        instance = create_single_instance()
        if not instance.acquire():
            print("\nODIN ya está ejecutándose. No se abrirá una segunda copia.")
            return

    config = Config()
    if "--set-language" in sys.argv:
        index = sys.argv.index("--set-language")
        language = (
            sys.argv[index + 1] if len(sys.argv) > index + 1 else "es-419"
        )
        selected = configure_language(config, language)
        print(f"Idioma de ODIN configurado: {selected}")
        return
    # En modo automatico OpenAI es el proveedor principal. No arrancamos
    # Ollama de forma preventiva porque su proceso local no es necesario y,
    # en algunas instalaciones de Windows, puede mostrar una consola fugaz.
    if not config.public_beta_no_ai and config.ai_provider == "ollama":
        ensure_ollama_server()
    key_import = import_key_file()
    if key_import.message:
        print(key_import.message)
    credential_directory = application_directory()
    for personal_import in (
        import_edsm_key_file(credential_directory),
        import_inara_key_file(
            credential_directory, journal_path=config.journal_path
        ),
    ):
        if personal_import.message:
            print(personal_import.message)

    if "--configure-voice" in sys.argv:
        run_voice_configuration(config)
        return

    if "--test-ai" in sys.argv:
        index = sys.argv.index("--test-ai")
        question = " ".join(sys.argv[index + 1:]).strip()
        if not question:
            question = "Presentate brevemente y confirmá que funcionás de forma local."
        try:
            print(OdinLocalAssistant(config=config).ask(question).text)
        except (OllamaError, OpenAIError, ValueError) as error:
            print(f"IA no disponible: {error}")
        return

    if "--test-openai" in sys.argv:
        try:
            model = OpenAIClient(model=config.openai_model).test_connection()
            print(f"OpenAI conectado correctamente ({model}).")
        except OpenAIError as error:
            print(f"OpenAI no disponible: {error}")
            raise SystemExit(1)
        return

    if "--test-voice" in sys.argv:
        index = sys.argv.index("--test-voice")
        officer = sys.argv[index + 1] if len(sys.argv) > index + 1 else "ODIN"
        text = " ".join(sys.argv[index + 2:]).strip() or "Sistemas de voz operativos, comandante."
        try:
            OfficerVoiceService(config).speak(officer, text)
        except VoiceServiceError as error:
            print(f"Voz no disponible: {error}")
        return

    if "--ask-odin" in sys.argv:
        index = sys.argv.index("--ask-odin")
        question = " ".join(sys.argv[index + 1:]).strip()
        try:
            answer = OdinLocalAssistant().ask(question).text
            print(answer)
            OfficerVoiceService(config).speak("ODIN", answer)
        except (OllamaError, OpenAIError, ValueError, VoiceServiceError) as error:
            print(f"ODIN no pudo responder: {error}")
        return

    if "--talk" in sys.argv:
        index = sys.argv.index("--talk")
        try:
            seconds = float(sys.argv[index + 1]) if len(sys.argv) > index + 1 else 7.0
            print(f"Escuchando durante {seconds:g} segundos. Hablá ahora...")
            question, answer = VoiceConversation(config).listen_once(seconds)
            print(f"Vos: {question}")
            print(f"ODIN: {answer}")
        except (
            ValueError, MicrophoneError, TranscriptionError, OllamaError,
            OpenAIError, VoiceServiceError,
        ) as error:
            print(f"Conversación por voz no disponible: {error}")
        return

    try:
        configure_diagnostics(config.data_root)
        odin = CommandCenter()
        if "--console" in sys.argv:
            odin.start()
        else:
            run_desktop(odin)
    except Exception:
        log_fatal_error()
        print(
            "\nODIN encontró un error inesperado. "
            f"Revisá el registro en: {config.data_root / 'logs' / 'odin.log'}"
        )
        if "--console" in sys.argv and sys.stdin and sys.stdin.isatty():
            input("Presioná Enter para cerrar...")
    finally:
        if instance is not None:
            instance.close()


if __name__ == "__main__":
    main()
