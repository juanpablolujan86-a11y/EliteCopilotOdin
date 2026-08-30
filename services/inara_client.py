"""Cliente aislado para la API oficial de Inara."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from core.version import VERSION
from services.inara_credentials import InaraCredentials


@dataclass(frozen=True, slots=True)
class InaraEventResult:
    accepted: bool
    retryable: bool
    status: int | None
    detail: str


@dataclass(frozen=True, slots=True)
class InaraSubmissionResult:
    accepted: bool
    retryable: bool
    status: int | None
    detail: str
    event_results: tuple[InaraEventResult, ...] = ()


class InaraClient:
    ENDPOINT = "https://inara.cz/inapi/v1/"
    SUCCESS_STATUSES = frozenset({200, 202, 204})

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def submit(
        self, credentials: InaraCredentials, events,
        *, is_being_developed: bool = True,
    ) -> InaraSubmissionResult:
        batch = list(events)
        if not batch or not all(isinstance(event, dict) for event in batch):
            raise ValueError("El lote Inara debe contener eventos válidos.")
        header = {
            "appName": "ODIN",
            "appVersion": VERSION,
            "isBeingDeveloped": bool(is_being_developed),
            "APIkey": credentials.api_key,
            "commanderName": credentials.commander_name,
        }
        if credentials.frontier_id:
            header["commanderFrontierID"] = credentials.frontier_id
        try:
            response = self.session.post(
                self.ENDPOINT,
                json={"header": header, "events": batch},
                headers={"Accept": "application/json", "User-Agent": f"ODIN/{VERSION}"},
                timeout=(5, 30),
            )
        except requests.RequestException as error:
            return InaraSubmissionResult(False, True, None, str(error))
        if response.status_code == 429 or response.status_code >= 500:
            return InaraSubmissionResult(
                False, True, int(response.status_code), "Servicio Inara no disponible"
            )
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return InaraSubmissionResult(
                False, True, int(response.status_code), "Respuesta no JSON de Inara"
            )
        return self._classify(payload)

    @classmethod
    def _classify(cls, payload) -> InaraSubmissionResult:
        if not isinstance(payload, dict):
            return InaraSubmissionResult(False, True, None, "Respuesta Inara inválida")
        header = payload.get("header")
        if not isinstance(header, dict):
            return InaraSubmissionResult(False, True, None, "Cabecera Inara ausente")
        header_status = header.get("eventStatus")
        details = [str(header.get("eventStatusText", ""))]
        event_statuses = []
        event_results = []
        for event in payload.get("events", []):
            if not isinstance(event, dict):
                return InaraSubmissionResult(False, True, None, "Evento Inara inválido")
            event_statuses.append(event.get("eventStatus"))
            event_detail = str(event.get("eventStatusText", "") or "")
            if event_detail:
                details.append(event_detail)
            event_status = event.get("eventStatus")
            event_results.append(InaraEventResult(
                accepted=event_status in cls.SUCCESS_STATUSES,
                retryable=not isinstance(event_status, int),
                status=int(event_status) if isinstance(event_status, int) else None,
                detail=event_detail,
            ))
        statuses = [header_status, *event_statuses]
        detail = " | ".join(item for item in details if item)[:500]
        if statuses and all(status in cls.SUCCESS_STATUSES for status in statuses):
            return InaraSubmissionResult(
                True, False, int(header_status), detail, tuple(event_results)
            )
        status = next((
            item for item in statuses
            if isinstance(item, int) and item not in cls.SUCCESS_STATUSES
        ), None)
        return InaraSubmissionResult(
            False, False, status, detail or "Solicitud rechazada",
            tuple(event_results),
        )
