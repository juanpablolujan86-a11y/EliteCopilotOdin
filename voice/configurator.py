"""Configurador de consola que nunca imprime ni guarda la API key en texto."""

from __future__ import annotations

import getpass

from core.config import Config
from voice.credentials import WindowsCredentialStore
from voice.edge import EDGE_LATIN_VOICES
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
        eleven_voices = ()
        secret = credentials.get()
        if secret:
            try:
                eleven_voices = tuple(
                    voice
                    for voice in ElevenLabsClient().list_voices(secret)
                    if voice.is_latin_spanish
                )
            except ElevenLabsError:
                pass
            finally:
                secret = ""
        for officer, assignment in settings.officers.items():
            provider = input(
                f"Proveedor de {officer} [edge/windows/elevenlabs] "
                f"({assignment.provider}): "
            ).strip().lower()
            if provider:
                if provider not in {"edge", "windows", "elevenlabs"}:
                    print(f"Proveedor inválido para {officer}; se conserva el anterior.")
                    continue
                assignment.provider = provider
            if assignment.provider == "edge":
                assignment.voice = EDGE_LATIN_VOICES[officer]
                print(f"Voz Edge latinoamericana asignada: {assignment.voice}")
            elif assignment.provider == "elevenlabs" and eleven_voices:
                print(f"\nVoces ElevenLabs verificadas en español latino para {officer}:")
                for number, voice in enumerate(eleven_voices, 1):
                    print(f"  {number}. {voice.name}")
                selection = input("Número de voz (Enter conserva la actual): ").strip()
                if selection.isdigit() and 1 <= int(selection) <= len(eleven_voices):
                    assignment.voice = eleven_voices[int(selection) - 1].voice_id
            else:
                voice = input(
                    f"Voz de Windows de {officer} ({assignment.voice}): "
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
