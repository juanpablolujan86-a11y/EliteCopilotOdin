"""
ODIN - Orbital Data Intelligence Nexus

exploration_context_builder.py

Construye el contexto de exploración de un sistema
a partir del evento FSDJump, la memoria local y EDSM.
"""

import json

from core.database import DatabaseManager
from models.exploration_context import ExplorationContext


class ExplorationContextBuilder:
    """
    Reúne la información conocida sobre un sistema.
    """

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def build(self, event: dict) -> ExplorationContext:
        """
        Construye y devuelve un ExplorationContext.
        """

        system_address = event.get("SystemAddress", 0)

        context = ExplorationContext(
            system_name=event.get("StarSystem", ""),
            system_address=system_address,
            population=event.get("Population", 0),
        )

        self._load_memory(context)
        self._load_edsm(context)

        return context

    def _load_memory(
        self,
        context: ExplorationContext,
    ) -> None:
        """
        Carga la información de visitas anteriores.
        """

        rows = self.database.query(
            """
            SELECT visit_count
            FROM visited_systems
            WHERE system_address = ?
            """,
            (context.system_address,),
        )

        context.first_visit = bool(
            rows
            and rows[0]["visit_count"] == 1
        )

    def _load_edsm(
        self,
        context: ExplorationContext,
    ) -> None:
        """
        Carga la última respuesta almacenada de EDSM.
        """

        rows = self.database.query(
            """
            SELECT
                found,
                response_json
            FROM edsm_system_cache
            WHERE system_address = ?
            """,
            (context.system_address,),
        )

        if not rows:
            return

        row = rows[0]

        context.edsm_found = row["found"] == 1

        if context.edsm_found and row["response_json"]:
            context.edsm_data = json.loads(
                row["response_json"]
            )