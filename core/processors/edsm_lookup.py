"""
ODIN - Orbital Data Intelligence Nexus

edsm_lookup.py

Consulta EDSM y guarda las respuestas en SQLite para evitar
consultas repetidas e innecesarias.
"""

import json
from datetime import datetime, timedelta, timezone

from core.database import DatabaseManager
from services.edsm_service import EDSMService


class EDSMLookup:
    """
    Consulta información de sistemas en EDSM utilizando una caché local.
    """

    CACHE_DURATION = timedelta(hours=24)

    def __init__(
        self,
        edsm_service: EDSMService,
        database: DatabaseManager
    ) -> None:
        self.edsm_service = edsm_service
        self.database = database
        self._create_table()

    def _create_table(self) -> None:
        self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS edsm_system_cache
            (
                system_address INTEGER PRIMARY KEY,
                system_name TEXT NOT NULL,
                found INTEGER NOT NULL,
                response_json TEXT,
                checked_at TEXT NOT NULL
            )
            """
        )

    def handle(self, event: dict) -> None:
        system_name = event.get("StarSystem")
        system_address = event.get("SystemAddress")

        if not system_name or system_address is None:
            print("EDSM                  : Datos del sistema incompletos")
            return

        cached_data = self._get_cached(system_address)

        if cached_data is not None:
            print("EDSM                  : Información obtenida de la memoria")
            self._show_result(cached_data)
            return

        print("EDSM                  : Consultando sistema...")

        system_data = self.edsm_service.get_system(system_name)

        self._save_cache(
            system_address=system_address,
            system_name=system_name,
            system_data=system_data
        )

        if system_data is None:
            print("EDSM                  : Sistema sin datos registrados")
            return

        print("EDSM                  : Información recibida")
        self._show_result(system_data)

    def _get_cached(self, system_address: int) -> dict | None:
        rows = self.database.query(
            """
            SELECT
                found,
                response_json,
                checked_at
            FROM edsm_system_cache
            WHERE system_address = ?
            """,
            (system_address,)
        )

        if not rows:
            return None

        row = rows[0]

        checked_at = datetime.fromisoformat(row["checked_at"])
        now = datetime.now(timezone.utc)

        if now - checked_at > self.CACHE_DURATION:
            return None

        if row["found"] == 0:
            return {}

        return json.loads(row["response_json"])

    def _save_cache(
        self,
        system_address: int,
        system_name: str,
        system_data: dict | None
    ) -> None:
        found = 1 if system_data is not None else 0

        response_json = (
            json.dumps(system_data, ensure_ascii=False)
            if system_data is not None
            else None
        )

        checked_at = datetime.now(timezone.utc).isoformat()

        self.database.execute(
            """
            INSERT INTO edsm_system_cache
            (
                system_address,
                system_name,
                found,
                response_json,
                checked_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(system_address)
            DO UPDATE SET
                system_name = excluded.system_name,
                found = excluded.found,
                response_json = excluded.response_json,
                checked_at = excluded.checked_at
            """,
            (
                system_address,
                system_name,
                found,
                response_json,
                checked_at
            )
        )

    def _show_result(self, system_data: dict) -> None:
        if not system_data:
            print("EDSM                  : Sistema sin datos registrados")
            return

        information = system_data.get("information", {})

        print(
            "Lealtad               : "
            f"{information.get('allegiance', 'Desconocida')}"
        )
        print(
            "Seguridad             : "
            f"{information.get('security', 'Desconocida')}"
        )
        print(
            "Economía              : "
            f"{information.get('economy', 'Desconocida')}"
        )
        print(
            "Población EDSM        : "
            f"{information.get('population', 0):,}"
        )