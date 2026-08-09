"""Importa credenciales EDSM desde un TXT y elimina el secreto visible."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.edsm_credentials import EDSMCredentialStore


KEY_FILENAME = "EDSM_API_KEY.txt"
PLACEHOLDER = "PEGAR_API_KEY_AQUI"


@dataclass(frozen=True, slots=True)
class EDSMKeyImportResult:
    imported: bool = False
    message: str = ""


def import_edsm_key_file(
    directory: Path, credentials: EDSMCredentialStore | None = None
) -> EDSMKeyImportResult:
    path = directory / KEY_FILENAME
    if not path.exists():
        return EDSMKeyImportResult()
    try:
        values = _read_values(path)
    except OSError as error:
        return EDSMKeyImportResult(message=f"No se pudo leer {KEY_FILENAME}: {error}")
    commander = values.get("COMMANDER", "")
    api_key = values.get("API_KEY", "")
    if not commander or not api_key or api_key == PLACEHOLDER:
        return EDSMKeyImportResult()
    credentials = credentials or EDSMCredentialStore()
    try:
        credentials.set(commander, api_key)
        path.write_text(
            "# Credenciales migradas al Administrador de credenciales de Windows.\n"
            "COMMANDER=\n"
            f"API_KEY={PLACEHOLDER}\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as error:
        return EDSMKeyImportResult(message=f"Credenciales EDSM no importadas: {error}")
    finally:
        api_key = ""
    return EDSMKeyImportResult(True, "Credenciales personales de EDSM protegidas por Windows.")


def _read_values(path: Path) -> dict[str, str]:
    values = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().upper() in {"COMMANDER", "API_KEY"}:
            values[key.strip().upper()] = value.strip()
    return values
