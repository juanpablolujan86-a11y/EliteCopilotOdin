"""
ODIN - Orbital Data Intelligence Nexus

system_memory.py

Guarda y consulta el historial de sistemas visitados.
"""

from core.database import DatabaseManager


class SystemMemory:
    """
    Memoria de sistemas de ODIN.

    Recibe eventos FSDJump, registra cada sistema y determina
    si es la primera visita o un regreso.
    """

    def __init__(self, database: DatabaseManager):
        self.database = database
        self._create_table()

    def _create_table(self) -> None:
        """
        Crea la tabla de sistemas si todavía no existe.
        """

        self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS visited_systems
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_address INTEGER UNIQUE,
                system_name TEXT NOT NULL,
                first_visit TEXT NOT NULL,
                last_visit TEXT NOT NULL,
                visit_count INTEGER NOT NULL DEFAULT 1
            )
            """
        )

    def handle(self, event: dict) -> None:
        """
        Registra el sistema de un evento FSDJump.
        """

        system_name = event.get("StarSystem")
        system_address = event.get("SystemAddress")
        timestamp = event.get("timestamp")

        if not system_name or system_address is None or not timestamp:
            print("Memoria ODIN          : Datos del sistema incompletos")
            return

        rows = self.database.query(
            """
            SELECT
                system_name,
                first_visit,
                last_visit,
                visit_count
            FROM visited_systems
            WHERE system_address = ?
            """,
            (system_address,)
        )

        if not rows:
            self.database.execute(
                """
                INSERT INTO visited_systems
                (
                    system_address,
                    system_name,
                    first_visit,
                    last_visit,
                    visit_count
                )
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    system_address,
                    system_name,
                    timestamp,
                    timestamp
                )
            )

            print("Memoria ODIN          : Primera visita registrada")
            return

        previous_visit = rows[0]
        new_visit_count = previous_visit["visit_count"] + 1

        self.database.execute(
            """
            UPDATE visited_systems
            SET
                system_name = ?,
                last_visit = ?,
                visit_count = ?
            WHERE system_address = ?
            """,
            (
                system_name,
                timestamp,
                new_visit_count,
                system_address
            )
        )

        print(
            "Memoria ODIN          : "
            f"Visita número {new_visit_count} a este sistema"
        )
        print(
            "Última visita anterior: "
            f"{previous_visit['last_visit']}"
        )