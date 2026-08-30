"""Credenciales personales de Inara protegidas por Windows."""

from __future__ import annotations

import json
from dataclasses import dataclass

from security.secret_store import SecretStore, create_secret_store


INARA_CREDENTIAL_TARGET = "ODIN/InaraApiCredentials"


@dataclass(frozen=True, slots=True)
class InaraCredentials:
    commander_name: str
    frontier_id: str
    api_key: str


class InaraCredentialStore:
    def __init__(self, store: SecretStore | None = None) -> None:
        self.store = store or create_secret_store(INARA_CREDENTIAL_TARGET)

    def set(self, commander_name: str, api_key: str, frontier_id: str = "") -> None:
        commander = str(commander_name).strip()
        secret = str(api_key).strip()
        fid = str(frontier_id).strip()
        if not commander:
            raise ValueError("El nombre del comandante de Inara es obligatorio.")
        if not secret:
            raise ValueError("La clave API de Inara es obligatoria.")
        self.store.set(json.dumps(
            {"commander_name": commander, "frontier_id": fid, "api_key": secret},
            ensure_ascii=False, separators=(",", ":"),
        ))

    def get(self) -> InaraCredentials | None:
        payload = self.store.get()
        if not payload:
            return None
        try:
            data = json.loads(payload)
            commander = str(data.get("commander_name", "")).strip()
            fid = str(data.get("frontier_id", "")).strip()
            secret = str(data.get("api_key", "")).strip()
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None
        if not commander or not secret:
            return None
        return InaraCredentials(commander, fid, secret)

    def delete(self) -> bool:
        return self.store.delete()

    def exists(self) -> bool:
        return self.get() is not None
