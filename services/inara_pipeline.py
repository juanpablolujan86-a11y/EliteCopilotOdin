"""Captura optativa y traducción del Journal para Inara."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from services.inara_events import InaraEventMapper
from services.inara_outbox import InaraOutbox


class InaraJournalPipeline:
    def __init__(self, outbox: InaraOutbox, mapper=None) -> None:
        self.outbox = outbox
        self.mapper = mapper or InaraEventMapper()
        self.logger = logging.getLogger("odin.inara")

    def capture(self, journal_event: dict, *, cargo_file: Path | None = None) -> int:
        queued = 0
        try:
            journal_event = self._with_cargo_inventory(journal_event, cargo_file)
            for event in self.mapper.map(journal_event):
                queued += int(self.outbox.enqueue(event))
        except (json.JSONDecodeError, sqlite3.Error, OSError, TypeError, ValueError):
            self.logger.exception("No se pudo conservar un evento para Inara")
        return queued

    @staticmethod
    def _with_cargo_inventory(event: dict, cargo_file: Path | None) -> dict:
        if event.get("event") != "Cargo" or cargo_file is None:
            return event
        snapshot = json.loads(Path(cargo_file).read_text(encoding="utf-8-sig"))
        inventory = snapshot.get("Inventory")
        if not isinstance(inventory, list):
            raise ValueError("Cargo.json no contiene un inventario válido")
        return {**event, "Inventory": inventory}
