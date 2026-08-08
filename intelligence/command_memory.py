"""Memoria local de expresiones de voz propias de cada comandante."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from core.database import DatabaseManager


@dataclass(frozen=True, slots=True)
class LearnedCommand:
    intent: str
    payload: dict[str, str]


def normalize_phrase(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


class VoiceCommandMemory:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def resolve(self, commander: str, phrase: str) -> LearnedCommand | None:
        rows = self.database.query(
            """
            SELECT intent, payload_json
            FROM voice_command_memory
            WHERE commander_key=? AND normalized_phrase=? AND enabled=1
            """,
            (commander, normalize_phrase(phrase)),
        )
        if not rows:
            return None
        row = rows[0]
        self.database.execute(
            """
            UPDATE voice_command_memory
            SET use_count=use_count+1, last_used_at=?
            WHERE commander_key=? AND normalized_phrase=?
            """,
            (self._now(), commander, normalize_phrase(phrase)),
        )
        return LearnedCommand(row["intent"], json.loads(row["payload_json"]))

    def remember(
        self, commander: str, phrase: str, intent: str, payload: dict[str, str]
    ) -> None:
        normalized = normalize_phrase(phrase)
        if not normalized:
            return
        now = self._now()
        self.database.execute(
            """
            INSERT INTO voice_command_memory
                (commander_key, normalized_phrase, original_phrase, intent,
                 payload_json, use_count, confirmation_count, enabled,
                 created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, 1, 0, 1, ?, ?)
            ON CONFLICT(commander_key, normalized_phrase) DO UPDATE SET
                original_phrase=excluded.original_phrase,
                intent=excluded.intent,
                payload_json=excluded.payload_json,
                use_count=voice_command_memory.use_count+1,
                enabled=1,
                last_used_at=excluded.last_used_at
            """,
            (commander, normalized, phrase.strip(), intent, json.dumps(payload), now, now),
        )

    def confirm(self, commander: str, phrase: str) -> bool:
        normalized = normalize_phrase(phrase)
        rows = self.database.query(
            "SELECT 1 FROM voice_command_memory WHERE commander_key=? AND normalized_phrase=?",
            (commander, normalized),
        )
        if not rows:
            return False
        self.database.execute(
            """UPDATE voice_command_memory
               SET confirmation_count=confirmation_count+1, enabled=1
               WHERE commander_key=? AND normalized_phrase=?""",
            (commander, normalized),
        )
        return True

    def forget(self, commander: str, phrase: str) -> bool:
        normalized = normalize_phrase(phrase)
        rows = self.database.query(
            "SELECT 1 FROM voice_command_memory WHERE commander_key=? AND normalized_phrase=?",
            (commander, normalized),
        )
        if not rows:
            return False
        self.database.execute(
            "DELETE FROM voice_command_memory WHERE commander_key=? AND normalized_phrase=?",
            (commander, normalized),
        )
        return True

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
