"""Credenciales personales de EDSM protegidas por Windows."""

from __future__ import annotations

import json
from dataclasses import dataclass

from security.secret_store import SecretStore, create_secret_store


EDSM_CREDENTIAL_TARGET = "ODIN/EDSMApiCredentials"


@dataclass(frozen=True, slots=True)
class EDSMCredentials:
    commander_name: str
    api_key: str


class EDSMCredentialStore:
    def __init__(self, store: SecretStore | None = None) -> None:
        self.store = store or create_secret_store(EDSM_CREDENTIAL_TARGET)

    def set(self, commander_name: str, api_key: str) -> None:
        commander = str(commander_name).strip()
        secret = str(api_key).strip()
        if not commander:
            raise ValueError("El nombre del comandante de EDSM es obligatorio.")
        if not secret:
            raise ValueError("La clave API de EDSM es obligatoria.")
        self.store.set(json.dumps(
            {"commander_name": commander, "api_key": secret},
            ensure_ascii=False, separators=(",", ":"),
        ))

    def get(self) -> EDSMCredentials | None:
        payload = self.store.get()
        if not payload:
            return None
        try:
            data = json.loads(payload)
            commander = str(data.get("commander_name", "")).strip()
            secret = str(data.get("api_key", "")).strip()
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None
        if not commander or not secret:
            return None
        return EDSMCredentials(commander, secret)

    def delete(self) -> bool:
        return self.store.delete()

    def exists(self) -> bool:
        return self.get() is not None
