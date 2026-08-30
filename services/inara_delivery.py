"""Trabajador optativo de entrega por lotes a Inara."""

from __future__ import annotations

import logging
import threading

from core.database import DatabaseManager
from services.inara_client import InaraClient
from services.inara_credentials import InaraCredentialStore
from services.inara_outbox import InaraOutbox


class InaraDeliveryService:
    def __init__(
        self, data_root, *, credentials_factory=InaraCredentialStore,
        client_factory=InaraClient, poll_seconds: float = 60.0,
    ) -> None:
        self.data_root = data_root
        self.credentials_factory = credentials_factory
        self.client_factory = client_factory
        self.poll_seconds = max(30.0, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.logger = logging.getLogger("odin.inara")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="odin-inara-delivery", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def process_once(self, *, now=None) -> int:
        credentials = self.credentials_factory().get()
        if credentials is None:
            return 0
        database = DatabaseManager(self.data_root)
        database.connect()
        try:
            database.create_tables()
            outbox = InaraOutbox(database)
            batch = outbox.due(now=now)
            if not batch:
                return 0
            result = self.client_factory().submit(
                credentials, [item.event for item in batch],
                is_being_developed=True,
            )
            if result.event_results and len(result.event_results) == len(batch):
                accepted = []
                retryable = []
                rejected = []
                for item, event_result in zip(batch, result.event_results):
                    if event_result.accepted:
                        accepted.append(item)
                    elif event_result.retryable:
                        retryable.append((item, event_result.detail))
                    else:
                        rejected.append((item, event_result))
                if accepted:
                    outbox.mark_sent(accepted, now=now)
                    self.logger.info("INARA_ACCEPTED | eventos=%s", len(accepted))
                for item, detail in retryable:
                    outbox.mark_failed((item,), detail or "Respuesta incompleta", now=now)
                for item, event_result in rejected:
                    detail = " ".join(str(event_result.detail).split())[:500]
                    outbox.mark_rejected((item,), detail, now=now)
                    self.logger.error(
                        "INARA_REJECTED | evento=%s | codigo=%s | detalle=%s",
                        item.event_name, event_result.status, detail,
                    )
                return len(batch)
            if result.accepted:
                outbox.mark_sent(batch, now=now)
                self.logger.info("INARA_ACCEPTED | eventos=%s", len(batch))
            elif result.retryable:
                outbox.mark_failed(batch, result.detail, now=now)
                self.logger.warning("INARA_RETRY | eventos=%s", len(batch))
            else:
                outbox.mark_rejected(batch, result.detail, now=now)
                detail = " ".join(str(result.detail).split())[:500]
                self.logger.error(
                    "INARA_REJECTED | eventos=%s | codigo=%s | detalle=%s",
                    len(batch), result.status, detail,
                )
            return len(batch)
        finally:
            database.disconnect()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.process_once()
            except Exception:
                self.logger.exception("Fallo inesperado en la sincronización Inara")
            self._stop.wait(self.poll_seconds)
