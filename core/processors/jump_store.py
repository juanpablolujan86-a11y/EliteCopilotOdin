"""
ODIN - Orbital Data Intelligence Nexus

jump_store.py

Guarda los eventos FSDJump en la base de datos SQLite.
"""

import json

from core.database import DatabaseManager


class JumpStore:
    """
    Almacena en SQLite los saltos detectados por ODIN.
    """

    def __init__(self, database: DatabaseManager):
        self.database = database

    def handle(self, event: dict) -> None:
        timestamp = event.get("timestamp")
        event_name = event.get("event")

        if not timestamp or not event_name:
            return

        event_json = json.dumps(
            event,
            ensure_ascii=False
        )

        self.database.execute(
            """
            INSERT INTO journal_events (
                timestamp,
                event,
                json
            )
            VALUES (?, ?, ?)
            """,
            (
                timestamp,
                event_name,
                event_json
            )
        )

        print("Memoria ODIN          : Salto guardado en SQLite")