"""Trabajador optativo de entrega privada a EDSM."""

from __future__ import annotations

import logging
import threading

from core.database import DatabaseManager
from services.edsm_credentials import EDSMCredentialStore
from services.edsm_discard import EDSMDiscardRegistry
from services.edsm_journal import EDSMJournalClient
from services.edsm_outbox import EDSMOutbox


class EDSMDeliveryService:
    def __init__(
        self, data_root, *, credentials_factory=EDSMCredentialStore,
        client_factory=EDSMJournalClient, discard_registry=None,
        poll_seconds: float = 10.0,
    ) -> None:
        self.data_root = data_root
        self.credentials_factory = credentials_factory
        self.client_factory = client_factory
        self.discard_registry = discard_registry or EDSMDiscardRegistry(data_root)
        self.poll_seconds = max(5.0, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.logger = logging.getLogger("odin.edsm")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="odin-edsm-delivery", daemon=True
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
            outbox = EDSMOutbox(database)
            due = outbox.due(now=now)
            if not due:
                return 0
            version, build = due[0].game_version, due[0].game_build
            batch = tuple(
                item for item in due
                if item.game_version == version and item.game_build == build
            )
            result = self.client_factory().submit(
                credentials, [item.event for item in batch],
                game_version=version, game_build=build,
            )
            if result.accepted:
                outbox.mark_sent(batch, now=now)
                self.logger.info("EDSM_ACCEPTED | eventos=%s", len(batch))
            elif result.retryable:
                outbox.mark_failed(batch, result.detail, now=now)
                self.logger.warning("EDSM_RETRY | eventos=%s", len(batch))
            else:
                outbox.mark_rejected(batch, result.detail, now=now)
                self.logger.error("EDSM_REJECTED | eventos=%s | codigo=%s",
                                  len(batch), result.code)
            return len(batch)
        finally:
            database.disconnect()

    def _run(self) -> None:
        self.discard_registry.refresh()
        while not self._stop.is_set():
            try:
                self.process_once()
            except Exception:
                self.logger.exception("Fallo inesperado en la sincronización EDSM")
            self._stop.wait(self.poll_seconds)
