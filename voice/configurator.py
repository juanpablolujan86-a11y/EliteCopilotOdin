"""Configurador de consola que nunca imprime ni guarda la API key en texto."""

from __future__ import annotations

import getpass

from core.config import Config
from voice.credentials import WindowsCredentialStore
from voice.elevenlabs import ElevenLabsClient, ElevenLabsError
from voice.settings import VoiceSettingsRepository
from voice.windows_voices import list_windows_voices


def run_voice_configuration(config: Config | None = None) -> None:
    config = config or Config()
    credentials = WindowsCredentialStore()
    repository = VoiceSettingsRepository(config.data_root)
    settings = repository.load()
    voices = list_windows_voices()

    print("\nCONFIGURACIÓN SEGURA DE VOZ DE ODIN")
    print("-" * 50)
    print("Voces Windows disponibles:")
    for voice in voices:
        print(f"  - {voice.name} ({voice.language}, {voice.gender})")
    print("\nAsignación actual:")
    for officer, assignment in settings.officers.items():
        print(f"  - {officer}: {assignment.provider} / {assignment.voice or 'sin voz'}")
    print(
        "\nClave ElevenLabs: "
        + ("guardada en Windows" if credentials.exists() else "no configurada")
    )
    print("\n1. Guardar o reemplazar clave ElevenLabs")
    print("2. Eliminar clave ElevenLabs")
    print("3. Usar voces Windows recomendadas")
    print("4. Asignar proveedor y voz por oficial")
    print("5. Mostrar voces disponibles en mi cuenta de ElevenLabs")
    print("0. Salir")
    option = input("\nOpción: ").strip()

    if option == "1":
        secret = getpass.getpass("Nueva API key (entrada oculta): ").strip()
        try:
            try:
                voices = ElevenLabsClient().list_voices(secret)
                credentials.set(secret)
            except (ElevenLabsError, OSError, ValueError) as error:
                print(f"No se guardó la clave: {error}")
                return
        finally:
            secret = ""
        print(
            "Clave validada y protegida por Windows. "
            f"Voces disponibles: {len(voices)}."
        )
    elif option == "2":
        print("Clave eliminada." if credentials.delete() else "No había una clave guardada.")
    elif option == "3":
        available = {voice.name for voice in voices}
        recommendations = {
            "ODIN": "Microsoft Raul - Spanish (Mexico)",
            "MÍMIR": "Microsoft Sabina - Spanish (Mexico)",
            "HEIMDALL": "Microsoft Raul - Spanish (Mexico)",
        }
        for officer, name in recommendations.items():
            if name in available:
                settings.officers[officer].provider = "windows"
                settings.officers[officer].voice = name
        repository.save(settings)
        print("Voces locales recomendadas guardadas.")
    elif option == "4":
        for officer, assignment in settings.officers.items():
            provider = input(
                f"Proveedor de {officer} [windows/elevenlabs] "
                f"({assignment.provider}): "
            ).strip().lower()
            if provider:
                if provider not in {"windows", "elevenlabs"}:
                    print(f"Proveedor inválido para {officer}; se conserva el anterior.")
                    continue
                assignment.provider = provider
            voice = input(
                f"Voz o voice_id de {officer} ({assignment.voice}): "
            ).strip()
            if voice:
                assignment.voice = voice
        repository.save(settings)
        print("Asignaciones guardadas sin almacenar secretos.")
    elif option == "5":
        secret = credentials.get()
        if not secret:
            print("Primero configurá tu propia API key de ElevenLabs.")
            return
        try:
            voices = ElevenLabsClient().list_voices(secret)
        except ElevenLabsError as error:
            print(f"No se pudieron consultar las voces: {error}")
            return
        finally:
            secret = ""
        print("\nVoces disponibles en esta cuenta:")
        for voice in voices:
            print(f"  - {voice.name} [{voice.voice_id}] ({voice.category or 'sin categoría'})")
    elif option != "0":
        print("Opción inválida.")
