"""Canal local Journal -> normalizador -> cola persistente EDDN."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from core.database import DatabaseManager
from services.eddn_journal import EDDNJournalMessageBuilder
from services.eddn_outbox import EDDNOutbox


class EDDNJournalPipeline:
    """Captura eventos aptos; deliberadamente no contiene un cliente HTTP."""

    def __init__(
        self, builder: EDDNJournalMessageBuilder, outbox: EDDNOutbox
    ) -> None:
        self.builder = builder
        self.outbox = outbox

    @classmethod
    def create(
        cls, data_root: Path, database: DatabaseManager, software_version: str
    ) -> "EDDNJournalPipeline":
        uploader_id = cls._anonymous_uploader_id(data_root)
        return cls(
            EDDNJournalMessageBuilder(uploader_id, software_version),
            EDDNOutbox(database),
        )

    def capture(self, event: dict) -> bool:
        envelope = self.builder.prepare(event)
        return bool(envelope is not None and self.outbox.enqueue(envelope))

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
