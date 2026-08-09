"""Cliente aislado para la API Journal v1 de EDSM."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from core.version import VERSION
from services.edsm_credentials import EDSMCredentials


@dataclass(frozen=True, slots=True)
class EDSMSubmissionResult:
    accepted: bool
    retryable: bool
    code: int | None
    detail: str


class EDSMJournalClient:
    ENDPOINT = "https://www.edsm.net/api-journal-v1"
    MAX_BATCH = 100
    SUCCESS_CODES = frozenset({100, 101, 102, 103, 104})
    PERMANENT_CODES = frozenset({201, 202, 203})

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def submit(
        self, credentials: EDSMCredentials, messages,
        *, game_version: str, game_build: str,
    ) -> EDSMSubmissionResult:
        events = list(messages)
        if not 1 <= len(events) <= self.MAX_BATCH:
            raise ValueError("El lote EDSM debe contener entre 1 y 100 eventos.")
        if not all(isinstance(event, dict) for event in events):
            raise ValueError("Todos los eventos EDSM deben ser objetos Journal.")
        version = str(game_version)
        build = str(game_build)
        if not version.strip() or not build.strip():
            raise ValueError("EDSM requiere versión y build del juego.")
        if version.strip().startswith("3.8"):
            raise ValueError("EDSM no admite eventos de la galaxia Legacy 3.8.")
        payload = {
            "commanderName": credentials.commander_name,
            "apiKey": credentials.api_key,
            "fromSoftware": "ODIN",
            "fromSoftwareVersion": VERSION,
            "fromGameVersion": version,
            "fromGameBuild": build,
            "message": events,
        }
        try:
            response = self.session.post(
                self.ENDPOINT, json=payload, timeout=(5, 20)
            )
        except requests.RequestException as error:
            return EDSMSubmissionResult(False, True, None, str(error))
        if response.status_code == 429 or response.status_code >= 500:
            return EDSMSubmissionResult(
                False, True, int(response.status_code), "Servicio no disponible"
            )
        try:
            result = response.json()
        except (ValueError, TypeError):
            return EDSMSubmissionResult(
                False, response.status_code >= 500,
                int(response.status_code), "Respuesta JSON inválida",
            )
        return self._classify(result)

    @classmethod
    def _classify(cls, payload) -> EDSMSubmissionResult:
        entries = payload if isinstance(payload, list) else [payload]
        if not entries or not all(isinstance(item, dict) for item in entries):
            return EDSMSubmissionResult(False, False, None, "Respuesta EDSM inválida")
        codes = [item.get("msgnum") for item in entries]
        details = " | ".join(str(item.get("msg", "")) for item in entries)[:500]
        if all(code in cls.SUCCESS_CODES for code in codes):
            return EDSMSubmissionResult(True, False, int(codes[-1]), details)
        if any(code == 429 for code in codes):
            return EDSMSubmissionResult(False, True, 429, details)
        code = next((item for item in codes if isinstance(item, int)), None)
        return EDSMSubmissionResult(False, False, code, details)
