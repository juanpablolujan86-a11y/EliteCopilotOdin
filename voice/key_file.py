"""Importación transitoria de una API key personal desde un TXT local."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from voice.credentials import WindowsCredentialStore
from voice.elevenlabs import ElevenLabsClient, ElevenLabsError


KEY_FILENAME = "ELEVENLABS_API_KEY.txt"
EXAMPLE_FILENAME = "ELEVENLABS_API_KEY.example.txt"
PLACEHOLDER = "PEGAR_API_KEY_AQUI"


@dataclass(frozen=True, slots=True)
class KeyImportResult:
    imported: bool = False
    message: str = ""


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def ensure_key_file(directory: Path | None = None) -> Path:
    directory = directory or application_directory()
    target = directory / KEY_FILENAME
    if target.exists():
        return target
    example = directory / EXAMPLE_FILENAME
    try:
        if example.exists():
            shutil.copyfile(example, target)
        else:
            target.write_text(
                "# Pegá debajo tu propia API key de ElevenLabs.\n\n"
                f"{PLACEHOLDER}\n",
                encoding="utf-8",
            )
    except OSError:
        pass
    return target


def _read_candidate(path: Path) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line == PLACEHOLDER:
            continue
        if line.upper().startswith("API_KEY="):
            line = line.split("=", 1)[1].strip()
        return line or None
    return None


def import_key_file(
    directory: Path | None = None,
    credentials: WindowsCredentialStore | None = None,
    client: ElevenLabsClient | None = None,
) -> KeyImportResult:
    path = ensure_key_file(directory)
    try:
        secret = _read_candidate(path)
    except OSError as error:
        return KeyImportResult(message=f"No se pudo leer {KEY_FILENAME}: {error}")
    if not secret:
        return KeyImportResult()

    credentials = credentials or WindowsCredentialStore()
    client = client or ElevenLabsClient()
    try:
        client.list_voices(secret)
        credentials.set(secret)
        path.write_text(
            "# Clave migrada al Administrador de credenciales de Windows.\n"
            "# Para reemplazarla, pegá una nueva API key debajo.\n\n"
            f"{PLACEHOLDER}\n",
            encoding="utf-8",
        )
    except (ElevenLabsError, OSError, ValueError) as error:
        return KeyImportResult(message=f"La clave del TXT no fue importada: {error}")
    finally:
        secret = ""
    return KeyImportResult(True, "Clave personal de ElevenLabs protegida por Windows.")
