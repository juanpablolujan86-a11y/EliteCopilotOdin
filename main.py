import sys

from core.command_center import CommandCenter
from core.config import Config
from core.diagnostics import configure_diagnostics, log_fatal_error
from core.single_instance import SingleInstance
from intelligence.assistant import OdinLocalAssistant
from intelligence.ollama import OllamaError
from speech.conversation import VoiceConversation
from speech.recorder import MicrophoneError
from speech.whisper import TranscriptionError
from voice.configurator import run_voice_configuration
from voice.key_file import import_key_file
from voice.service import OfficerVoiceService, VoiceServiceError


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
        except (OllamaError, ValueError, VoiceServiceError) as error:
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
        except (ValueError, MicrophoneError, TranscriptionError, OllamaError, VoiceServiceError) as error:
            print(f"Conversación por voz no disponible: {error}")
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
