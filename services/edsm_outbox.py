"""Cola persistente aislada para futuros lotes Journal de EDSM."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.database import DatabaseManager


@dataclass(frozen=True, slots=True)
class EDSMOutboxItem:
    event_key: str
    event_type: str
    event: dict
    game_version: str
    game_build: str
    attempts: int


class EDSMOutbox:
    BASE_RETRY_SECONDS = 60
    MAX_RETRY_SECONDS = 3600

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def enqueue(
        self, event: dict, *, game_version: str, game_build: str,
        now: datetime | None = None,
    ) -> bool:
        if not isinstance(event, dict) or not event.get("event") or not event.get("timestamp"):
            return False
        version, build = str(game_version), str(game_build)
        if not version.strip() or not build.strip() or version.strip().startswith("3.8"):
            return False
        payload = json.dumps(
            event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        event_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if self.database.query(
            "SELECT 1 FROM edsm_outbox WHERE event_key=?", (event_key,)
        ):
            return False
        stamp = self._stamp(now or datetime.now(timezone.utc))
        self.database.execute(
            """INSERT INTO edsm_outbox
            (event_key,event_type,payload_json,game_version,game_build,status,
             attempts,next_attempt_at,created_at,sent_at,last_error)
            VALUES(?,?,?,?,?,'pending',0,?,?,NULL,'')""",
            (event_key, str(event["event"]), payload, version, build, stamp, stamp),
        )
        return True

    def due(self, *, limit: int = 100, now: datetime | None = None):
        stamp = self._stamp(now or datetime.now(timezone.utc))
        rows = self.database.query(
            """SELECT event_key,event_type,payload_json,game_version,game_build,attempts
            FROM edsm_outbox WHERE status='pending' AND next_attempt_at<=?
            ORDER BY created_at,event_key LIMIT ?""",
            (stamp, max(1, min(int(limit), 100))),
        )
        return tuple(EDSMOutboxItem(
            row["event_key"], row["event_type"], json.loads(row["payload_json"]),
            row["game_version"], row["game_build"], int(row["attempts"]),
        ) for row in rows)

    def mark_sent(self, items, *, now: datetime | None = None) -> None:
        stamp = self._stamp(now or datetime.now(timezone.utc))
        with self.database.transaction():
            for item in items:
                self.database.execute(
                    """UPDATE edsm_outbox SET status='sent',sent_at=?,last_error=''
                    WHERE event_key=? AND status='pending'""",
                    (stamp, item.event_key),
                )

    def mark_failed(
        self, items, error: Exception | str, *, now: datetime | None = None
    ) -> None:
        current = now or datetime.now(timezone.utc)
        with self.database.transaction():
            for item in items:
                attempts = item.attempts + 1
                delay = min(
                    self.MAX_RETRY_SECONDS,
                    self.BASE_RETRY_SECONDS * (2 ** (attempts - 1)),
                )
                self.database.execute(
                    """UPDATE edsm_outbox SET attempts=?,next_attempt_at=?,last_error=?
                    WHERE event_key=? AND status='pending'""",
                    (attempts, self._stamp(current + timedelta(seconds=delay)),
                     str(error)[:500], item.event_key),
                )

    def mark_rejected(
        self, items, error: Exception | str, *, now: datetime | None = None
    ) -> None:
        stamp = self._stamp(now or datetime.now(timezone.utc))
        with self.database.transaction():
            for item in items:
                self.database.execute(
                    """UPDATE edsm_outbox SET status='rejected',sent_at=?,last_error=?
                    WHERE event_key=? AND status='pending'""",
                    (stamp, str(error)[:500], item.event_key),
                )

    def counts(self) -> dict[str, int]:
        rows = self.database.query(
            "SELECT status,COUNT(*) quantity FROM edsm_outbox GROUP BY status"
        )
        return {row["status"]: int(row["quantity"]) for row in rows}

    @staticmethod
    def _stamp(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
