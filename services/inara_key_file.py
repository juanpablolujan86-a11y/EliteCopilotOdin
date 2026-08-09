"""Importa credenciales Inara desde TXT y elimina el secreto visible."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.inara_credentials import InaraCredentialStore


KEY_FILENAME = "INARA_API_KEY.txt"
PLACEHOLDER = "PEGAR_API_KEY_AQUI"


@dataclass(frozen=True, slots=True)
class InaraKeyImportResult:
    imported: bool = False
    message: str = ""


def import_inara_key_file(
    directory: Path, credentials: InaraCredentialStore | None = None
) -> InaraKeyImportResult:
    path = directory / KEY_FILENAME
    if not path.exists():
        return InaraKeyImportResult()
    try:
        values = _read_values(path)
    except OSError as error:
        return InaraKeyImportResult(message=f"No se pudo leer {KEY_FILENAME}: {error}")
    commander = values.get("COMMANDER", "")
    frontier_id = values.get("FRONTIER_ID", "")
    api_key = values.get("API_KEY", "")
    if not commander or not api_key or api_key == PLACEHOLDER:
        return InaraKeyImportResult()
    credentials = credentials or InaraCredentialStore()
    try:
        credentials.set(commander, api_key, frontier_id)
        path.write_text(
            "# Credenciales migradas al Administrador de credenciales de Windows.\n"
            "COMMANDER=\nFRONTIER_ID=\n"
            f"API_KEY={PLACEHOLDER}\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as error:
        return InaraKeyImportResult(message=f"Credenciales Inara no importadas: {error}")
    finally:
        api_key = ""
    return InaraKeyImportResult(True, "Credenciales personales de Inara protegidas por Windows.")


def _read_values(path: Path) -> dict[str, str]:
    values = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        if key in {"COMMANDER", "FRONTIER_ID", "API_KEY"}:
            values[key] = value.strip()
    return values
