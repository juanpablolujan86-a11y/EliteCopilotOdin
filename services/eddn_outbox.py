"""Cola SQLite persistente para futuros envios a EDDN."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.database import DatabaseManager


@dataclass(frozen=True, slots=True)
class EDDNOutboxItem:
    message_key: str
    event_type: str
    envelope: dict
    attempts: int
    next_attempt_at: str


class EDDNOutbox:
    """Conserva mensajes, deduplica y calcula reintentos sin transmitirlos."""

    BASE_RETRY_SECONDS = 15
    MAX_RETRY_SECONDS = 3600

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def enqueue(self, envelope: dict, *, now: datetime | None = None) -> bool:
        payload = json.dumps(
            envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        message_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if self.database.query(
            "SELECT 1 FROM eddn_outbox WHERE message_key=?", (message_key,)
        ):
            return False
        stamp = self._stamp(now or datetime.now(timezone.utc))
        event_type = str(envelope.get("message", {}).get("event", "") or "")
        self.database.execute(
            """INSERT INTO eddn_outbox
            (message_key,event_type,payload_json,status,attempts,next_attempt_at,
             created_at,sent_at,last_error) VALUES(?,?,?,'pending',0,?,?,NULL,'')""",
            (message_key, event_type, payload, stamp, stamp),
        )
        return True

    def due(
        self, *, limit: int = 50, now: datetime | None = None
    ) -> tuple[EDDNOutboxItem, ...]:
        stamp = self._stamp(now or datetime.now(timezone.utc))
        rows = self.database.query(
            """SELECT message_key,event_type,payload_json,attempts,next_attempt_at
            FROM eddn_outbox WHERE status='pending' AND next_attempt_at<=?
            ORDER BY created_at,message_key LIMIT ?""",
            (stamp, max(1, min(int(limit), 500))),
        )
        return tuple(
            EDDNOutboxItem(
                row["message_key"], row["event_type"],
                json.loads(row["payload_json"]), int(row["attempts"]),
                row["next_attempt_at"],
            )
            for row in rows
        )

    def mark_sent(
        self, message_key: str, *, now: datetime | None = None
    ) -> None:
        self.database.execute(
            """UPDATE eddn_outbox SET status='sent',sent_at=?,last_error=''
            WHERE message_key=? AND status='pending'""",
            (self._stamp(now or datetime.now(timezone.utc)), message_key),
        )

    def mark_failed(
        self, message_key: str, error: Exception | str,
        *, now: datetime | None = None,
    ) -> None:
        rows = self.database.query(
            "SELECT attempts FROM eddn_outbox WHERE message_key=? AND status='pending'",
            (message_key,),
        )
        if not rows:
            return
        attempts = int(rows[0]["attempts"]) + 1
        delay = min(
            self.MAX_RETRY_SECONDS,
            self.BASE_RETRY_SECONDS * (2 ** (attempts - 1)),
        )
        current = now or datetime.now(timezone.utc)
        self.database.execute(
            """UPDATE eddn_outbox SET attempts=?,next_attempt_at=?,last_error=?
            WHERE message_key=? AND status='pending'""",
            (
                attempts, self._stamp(current + timedelta(seconds=delay)),
                str(error)[:500], message_key,
            ),
        )

    def pending_count(self) -> int:
        row = self.database.query(
            "SELECT COUNT(*) quantity FROM eddn_outbox WHERE status='pending'"
        )[0]
        return int(row["quantity"])

    @staticmethod
    def _stamp(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
