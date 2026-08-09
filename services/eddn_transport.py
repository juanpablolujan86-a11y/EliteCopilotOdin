"""Transporte HTTP EDDN, desacoplado del bucle principal de ODIN."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass

import requests

from services.eddn_outbox import EDDNOutbox
from core.database import DatabaseManager


@dataclass(frozen=True, slots=True)
class EDDNDeliveryResult:
    accepted: bool
    retryable: bool
    status_code: int | None
    detail: str


class EDDNHTTPClient:
    ENDPOINT = "https://eddn.edcd.io:4430/upload/"

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def send(self, envelope: dict) -> EDDNDeliveryResult:
        body = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        try:
            response = self.session.post(
                self.ENDPOINT,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=(5, 15),
            )
        except requests.RequestException as error:
            return EDDNDeliveryResult(False, True, None, str(error))
        status = int(response.status_code)
        detail = str(getattr(response, "text", "") or "")[:500]
        if status == 200 and detail.strip() == "OK":
            return EDDNDeliveryResult(True, False, status, detail)
        if status in {408, 413, 429} or status >= 500:
            return EDDNDeliveryResult(False, True, status, detail)
        return EDDNDeliveryResult(False, False, status, detail)


class EDDNDeliveryWorker:
    def __init__(self, outbox: EDDNOutbox, client: EDDNHTTPClient) -> None:
        self.outbox = outbox
        self.client = client
        self.logger = logging.getLogger("odin.eddn")

    def run_once(self, *, limit: int = 25, now=None) -> int:
        processed = 0
        for item in self.outbox.due(limit=limit, now=now):
            result = self.client.send(item.envelope)
            if result.accepted:
                self.outbox.mark_sent(item.message_key, now=now)
                self.logger.info("EDDN_ACCEPTED | tipo=%s", item.event_type)
            elif result.retryable:
                self.outbox.mark_failed(item.message_key, result.detail, now=now)
                self.logger.warning(
                    "EDDN_RETRY | tipo=%s | estado=%s | intento=%s",
                    item.event_type, result.status_code, item.attempts + 1,
                )
            else:
                self.outbox.mark_rejected(item.message_key, result.detail, now=now)
                self.logger.error(
                    "EDDN_REJECTED | tipo=%s | estado=%s",
                    item.event_type, result.status_code,
                )
            processed += 1
        return processed


class EDDNDeliveryService:
    """Procesa la cola en otro hilo para no bloquear juego, voz ni Journal."""

    def __init__(
        self, data_root, *, client_factory=EDDNHTTPClient, poll_seconds: float = 5.0
    ) -> None:
        self.data_root = data_root
        self.client_factory = client_factory
        self.poll_seconds = max(1.0, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.logger = logging.getLogger("odin.eddn")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="odin-eddn-delivery", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def process_once(self, *, now=None) -> int:
        database = DatabaseManager(self.data_root)
        database.connect()
        try:
            database.create_tables()
            return EDDNDeliveryWorker(
                EDDNOutbox(database), self.client_factory()
            ).run_once(now=now)
        finally:
            database.disconnect()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.process_once()
            except Exception:
                self.logger.exception("Fallo inesperado procesando la cola EDDN")
            self._stop.wait(self.poll_seconds)
