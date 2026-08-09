"""Captura optativa y traducción del Journal para Inara."""

from __future__ import annotations

import logging
import sqlite3

from services.inara_events import InaraEventMapper
from services.inara_outbox import InaraOutbox


class InaraJournalPipeline:
    def __init__(self, outbox: InaraOutbox, mapper=None) -> None:
        self.outbox = outbox
        self.mapper = mapper or InaraEventMapper()
        self.logger = logging.getLogger("odin.inara")

    def capture(self, journal_event: dict) -> int:
        queued = 0
        try:
            for event in self.mapper.map(journal_event):
                queued += int(self.outbox.enqueue(event))
        except (sqlite3.Error, OSError, TypeError, ValueError):
            self.logger.exception("No se pudo conservar un evento para Inara")
        return queued
