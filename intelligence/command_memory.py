"""Memoria local de expresiones de voz propias de cada comandante."""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
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
    words = re.findall(r"[a-z0-9]+", plain)
    if words and words[0] in {"odin", "olin", "odim", "odyn", "bodin", "vodin"}:
        words.pop(0)
    return " ".join(words)


class VoiceCommandMemory:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def resolve(self, commander: str, phrase: str) -> LearnedCommand | None:
        normalized = normalize_phrase(phrase)
        rows = self.database.query(
            """
            SELECT normalized_phrase, intent, payload_json
            FROM voice_command_memory
            WHERE commander_key=? AND normalized_phrase=? AND enabled=1
            """,
            (commander, normalized),
        )
        if not rows:
            candidates = self.database.query(
                """SELECT normalized_phrase, original_phrase, intent, payload_json
                   FROM voice_command_memory
                   WHERE commander_key=? AND enabled=1""",
                (commander,),
            )
            ranked = sorted(
                [
                    (
                    max(
                        SequenceMatcher(
                            None, normalized, normalize_phrase(row["original_phrase"])
                        ).ratio(),
                        self._semantic_score(normalized, row),
                    ),
                    row,
                    )
                for row in candidates
                if normalized
                ],
                key=lambda item: item[0],
                reverse=True,
            )
            if not ranked or ranked[0][0] < 0.88:
                return None
            if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08:
                return None
            rows = [ranked[0][1]]
        row = rows[0]
        self.database.execute(
            """
            UPDATE voice_command_memory
            SET use_count=use_count+1, last_used_at=?
            WHERE commander_key=? AND normalized_phrase=?
            """,
            (self._now(), commander, row["normalized_phrase"]),
        )
        return LearnedCommand(row["intent"], json.loads(row["payload_json"]))

    @staticmethod
    def _semantic_score(normalized: str, row) -> float:
        if row["intent"] != "home_route":
            return 0.0
        words = set(normalized.split())
        learned = set(normalize_phrase(row["original_phrase"]).split())
        movement = any(
            word.startswith(("llev", "viaj", "regres", "volv"))
            or word in {"vamos", "ir", "ruta"}
            for word in words
        )
        ignored = {
            "el", "la", "a", "al", "de", "me", "dejame", "debame",
            "llevame", "vamos", "ir", "ruta",
        }
        aliases = (words & learned) - ignored
        return 0.90 if movement and aliases else 0.0

    def remember(
        self, commander: str, phrase: str, intent: str, payload: dict[str, str],
        *, source: str = "adaptive",
    ) -> None:
        normalized = normalize_phrase(phrase)
        if not normalized:
            return
        now = self._now()
        self.database.execute(
            """
            INSERT INTO voice_command_memory
                (commander_key, normalized_phrase, original_phrase, intent,
                 payload_json, use_count, confirmation_count, enabled, source,
                 created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, 1, 0, 1, ?, ?, ?)
            ON CONFLICT(commander_key, normalized_phrase) DO UPDATE SET
                original_phrase=excluded.original_phrase,
                intent=excluded.intent,
                payload_json=excluded.payload_json,
                source=excluded.source,
                use_count=voice_command_memory.use_count+1,
                enabled=1,
                last_used_at=excluded.last_used_at
            """,
            (
                commander, normalized, phrase.strip(), intent,
                json.dumps(payload), source, now, now,
            ),
        )

    def count(self, commander: str, *, source: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM voice_command_memory WHERE commander_key=?"
        parameters: tuple = (commander,)
        if source is not None:
            query += " AND source=?"
            parameters = (commander, source)
        return int(self.database.query(query, parameters)[0][0])

    def forget_commander(self, commander: str) -> int:
        count = self.count(commander)
        self.database.execute(
            "DELETE FROM voice_command_memory WHERE commander_key=?", (commander,)
        )
        return count

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
