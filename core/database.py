"""
ODIN - Orbital Data Intelligence Nexus

database.py

Administrador central de SQLite.
"""

from pathlib import Path
import sqlite3
from sqlite3 import Connection


class DatabaseManager:
    """
    Gestiona la base de datos local de ODIN.
    """

    def __init__(self, data_root: Path):
        self.database_folder = data_root / "database"
        self.database_folder.mkdir(parents=True, exist_ok=True)

        self.database_file = self.database_folder / "odin.db"
        self.connection: Connection | None = None

    def connect(self) -> None:
        if self.connection is None:
            self.connection = sqlite3.connect(self.database_file)
            self.connection.row_factory = sqlite3.Row

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str, parameters: tuple = ()) -> None:
        if self.connection is None:
            raise RuntimeError("La base de datos no está conectada.")

        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        self.connection.commit()

    def query(self, sql: str, parameters: tuple = ()) -> list:
        if self.connection is None:
            raise RuntimeError("La base de datos no está conectada.")

        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        return cursor.fetchall()

    def create_tables(self) -> None:
        """
        Crea todas las tablas principales de ODIN.
        """

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS commander
            (
                id INTEGER PRIMARY KEY,
                name TEXT,
                fid TEXT,
                created_at TEXT
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_events
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event TEXT NOT NULL,
                json TEXT NOT NULL
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS stellar_bodies
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_address INTEGER NOT NULL,
                system_name TEXT NOT NULL,
                body_id INTEGER NOT NULL,
                body_name TEXT NOT NULL,
                body_type TEXT NOT NULL,
                subtype TEXT,
                is_moon INTEGER NOT NULL DEFAULT 0,
                terraformable INTEGER NOT NULL DEFAULT 0,
                atmosphere TEXT,
                volcanism TEXT,
                gravity REAL,
                radius REAL,
                distance_from_arrival REAL,
                was_discovered INTEGER NOT NULL DEFAULT 0,
                was_mapped INTEGER NOT NULL DEFAULT 0,
                was_footfalled INTEGER NOT NULL DEFAULT 0,
                landable INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL,
                scanned_at TEXT NOT NULL,

                UNIQUE(system_address, body_id)
            )
            """
        )

        self._ensure_column(
            "stellar_bodies",
            "was_footfalled",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "stellar_bodies",
            "landable",
            "INTEGER NOT NULL DEFAULT 0",
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS system_exploration
            (
                system_address INTEGER PRIMARY KEY,
                system_name TEXT NOT NULL,
                expected_body_count INTEGER NOT NULL DEFAULT 0,
                discovered_body_count INTEGER NOT NULL DEFAULT 0,
                star_count INTEGER NOT NULL DEFAULT 0,
                planet_count INTEGER NOT NULL DEFAULT 0,
                moon_count INTEGER NOT NULL DEFAULT 0,
                terraformable_count INTEGER NOT NULL DEFAULT 0,
                mapped_count INTEGER NOT NULL DEFAULT 0,
                biology_signal_count INTEGER NOT NULL DEFAULT 0,
                organic_sample_count INTEGER NOT NULL DEFAULT 0,
                all_bodies_found INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS mapped_bodies
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_address INTEGER NOT NULL,
                body_id INTEGER NOT NULL,
                body_name TEXT,
                probes_used INTEGER,
                efficiency_target INTEGER,
                efficiency_bonus INTEGER NOT NULL DEFAULT 0,
                mapped_at TEXT NOT NULL,

                UNIQUE(system_address, body_id)
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS biological_signals
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_address INTEGER NOT NULL,
                body_id INTEGER,
                body_name TEXT,
                source_event TEXT NOT NULL,
                signal_type TEXT,
                signal_count INTEGER NOT NULL DEFAULT 0,
                genus TEXT,
                species TEXT,
                variant TEXT,
                scan_type TEXT,
                was_logged INTEGER,
                recorded_at TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS expedition_items
            (
                event_key TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                system_address INTEGER,
                system_name TEXT,
                body_id INTEGER,
                description TEXT,
                base_value INTEGER NOT NULL DEFAULT 0,
                potential_value INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                recorded_at TEXT NOT NULL
            )
            """
        )

        self._ensure_column(
            "expedition_items",
            "status",
            "TEXT NOT NULL DEFAULT 'pending'",
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS expedition_sales
            (
                event_key TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                value INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS mimir_first_footfalls
            (
                system_address INTEGER NOT NULL,
                body_id INTEGER NOT NULL,
                body_name TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                PRIMARY KEY (system_address, body_id)
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS heimdall_navigation_state
            (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS heimdall_planned_routes
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_system TEXT NOT NULL,
                destination_system TEXT NOT NULL,
                provider TEXT NOT NULL,
                strategy TEXT NOT NULL,
                jump_range REAL NOT NULL,
                efficiency INTEGER NOT NULL,
                total_jumps INTEGER NOT NULL,
                distance REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                current_waypoint_index INTEGER NOT NULL DEFAULT 1,
                jumps_completed INTEGER NOT NULL DEFAULT 0,
                json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        self._ensure_column(
            "heimdall_planned_routes",
            "current_waypoint_index",
            "INTEGER NOT NULL DEFAULT 1",
        )
        self._ensure_column(
            "heimdall_planned_routes",
            "jumps_completed",
            "INTEGER NOT NULL DEFAULT 0",
        )

        self._ensure_column(
            "biological_signals",
            "was_logged",
            "INTEGER",
        )

        # Versiones anteriores guardaban el nombre localizado (Biológica).
        # Se normaliza para que los filtros sean independientes del idioma.
        self.execute(
            """
            UPDATE biological_signals
            SET signal_type = 'Biological'
            WHERE LOWER(COALESCE(signal_type, '')) LIKE 'biol%'
              AND source_event IN ('FSSBodySignals', 'SAASignalsFound')
            """
        )

        self.execute(
            """
            UPDATE system_exploration
            SET organic_sample_count = (
                SELECT COUNT(*)
                FROM biological_signals
                WHERE biological_signals.system_address =
                    system_exploration.system_address
                  AND source_event = 'ScanOrganic'
                  AND scan_type = 'Analyse'
            )
            """
        )

    def _ensure_column(
        self,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        """Añade una columna a bases existentes sin perder datos."""

        existing = {
            row["name"]
            for row in self.query(f"PRAGMA table_info({table})")
        }

        if column not in existing:
            self.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )
