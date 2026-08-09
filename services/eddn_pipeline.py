"""Canal local Journal -> normalizador -> cola persistente EDDN."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import json
import logging
import sqlite3

from core.database import DatabaseManager
from services.eddn_journal import EDDNJournalMessageBuilder
from services.eddn_commodity import EDDNCommodityMessageBuilder
from services.eddn_outbox import EDDNOutbox


class EDDNJournalPipeline:
    """Captura eventos aptos; deliberadamente no contiene un cliente HTTP."""

    def __init__(
        self, builder: EDDNJournalMessageBuilder, outbox: EDDNOutbox
    ) -> None:
        self.builder = builder
        self.commodity_builder = EDDNCommodityMessageBuilder(builder)
        self.outbox = outbox
        self.logger = logging.getLogger("odin.eddn")

    @classmethod
    def create(
        cls, data_root: Path, database: DatabaseManager, software_version: str,
        *, test_mode: bool = True,
    ) -> "EDDNJournalPipeline":
        uploader_id = cls._anonymous_uploader_id(data_root)
        return cls(
            EDDNJournalMessageBuilder(
                uploader_id, software_version, test_mode=test_mode
            ),
            EDDNOutbox(database),
        )

    def capture(self, event: dict, *, market_file: Path | None = None) -> bool:
        if event.get("event") == "Market":
            envelope = self._prepare_market(event, market_file)
        else:
            envelope = self.builder.prepare(event)
        if envelope is None:
            return False
        try:
            return self.outbox.enqueue(envelope)
        except (sqlite3.Error, OSError, ValueError):
            self.logger.exception("No se pudo conservar un evento en la cola EDDN")
            return False

    def _prepare_market(self, event: dict, market_file: Path | None):
        if market_file is None:
            return None
        try:
            payload = json.loads(market_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            self.logger.exception("No se pudo leer Market.json para EDDN")
            return None
        return self.commodity_builder.prepare(event, payload)

    def bootstrap_journal(self, journal: Path) -> None:
        """Recupera metadatos/contexto sin encolar información histórica."""

        fileheader = None
        load_game = None
        location = None
        try:
            with journal.open("r", encoding="utf-8", errors="ignore") as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    kind = event.get("event")
                    if kind == "Fileheader" and fileheader is None:
                        fileheader = event
                    elif kind == "LoadGame":
                        load_game = event
                    elif kind in {"Location", "FSDJump", "CarrierJump"}:
                        location = event
        except OSError:
            return
        for event in (fileheader, load_game, location):
            if event is not None:
                self.builder.prepare(event)

    @staticmethod
    def _anonymous_uploader_id(data_root: Path) -> str:
        identity_path = data_root / "community" / "eddn_uploader_id.txt"
        try:
            existing = identity_path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity = f"odin-{uuid4()}"
        temporary = identity_path.with_suffix(".tmp")
        temporary.write_text(identity, encoding="utf-8")
        temporary.replace(identity_path)
        return identity
