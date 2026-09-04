"""
ODIN - Orbital Data Intelligence Nexus

database.py

Administrador central de SQLite.
"""

from pathlib import Path
import sqlite3
from sqlite3 import Connection
from contextlib import contextmanager
import threading


class DatabaseManager:
    """
    Gestiona la base de datos local de ODIN.
    """

    def __init__(self, data_root: Path):
        self.database_folder = data_root / "database"
        self.database_folder.mkdir(parents=True, exist_ok=True)

        self.database_file = self.database_folder / "odin.db"
        self.connection: Connection | None = None
        self._transaction_depth = 0
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            if self.connection is None:
                self.connection = sqlite3.connect(
                    self.database_file, timeout=30.0, check_same_thread=False,
                )
                self.connection.row_factory = sqlite3.Row
                self.connection.execute("PRAGMA busy_timeout = 30000")
                self.connection.execute("PRAGMA journal_mode = WAL")
                self.connection.execute("PRAGMA synchronous = NORMAL")

    def disconnect(self) -> None:
        with self._lock:
            if self.connection is not None:
                self.connection.close()
                self.connection = None

    def execute(self, sql: str, parameters: tuple = ()) -> None:
        with self._lock:
            if self.connection is None:
                raise RuntimeError("La base de datos no está conectada.")
            cursor = self.connection.cursor()
            cursor.execute(sql, parameters)
            if self._transaction_depth == 0:
                self.connection.commit()

    @contextmanager
    def transaction(self):
        with self._lock:
            if self.connection is None:
                raise RuntimeError("La base de datos no est\u00e1 conectada.")
            outermost = self._transaction_depth == 0
            self._transaction_depth += 1
            try:
                yield
                self._transaction_depth -= 1
                if outermost:
                    self.connection.commit()
            except Exception:
                self._transaction_depth -= 1
                if outermost:
                    self.connection.rollback()
                raise

    def query(self, sql: str, parameters: tuple = ()) -> list:
        with self._lock:
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
        self.execute("""CREATE TABLE IF NOT EXISTS freyja_inventory
        (commodity TEXT PRIMARY KEY, localised_name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0, total_cost INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        self.execute("""CREATE TABLE IF NOT EXISTS freyja_trade_events
        (event_key TEXT PRIMARY KEY, timestamp TEXT NOT NULL, event_type TEXT NOT NULL,
        market_id INTEGER, commodity TEXT NOT NULL, localised_name TEXT,
        quantity INTEGER NOT NULL DEFAULT 0, unit_price INTEGER NOT NULL DEFAULT 0,
        total_value INTEGER NOT NULL DEFAULT 0, realized_profit INTEGER NOT NULL DEFAULT 0,
        cost_known INTEGER NOT NULL DEFAULT 0, raw_json TEXT NOT NULL)""")
        self.execute("""CREATE TABLE IF NOT EXISTS freyja_markets
        (market_id INTEGER PRIMARY KEY, system_name TEXT NOT NULL, station_name TEXT NOT NULL,
        updated_at TEXT NOT NULL, source TEXT NOT NULL)""")
        for column, definition in (
            ("x","REAL"),("y","REAL"),("z","REAL"),
            ("distance_to_arrival","REAL"),("has_large_pad","INTEGER NOT NULL DEFAULT 0"),
            ("is_planetary","INTEGER NOT NULL DEFAULT 0"),
            ("power_name","TEXT NOT NULL DEFAULT ''"),
            ("power_state","TEXT NOT NULL DEFAULT ''"),
            ("station_type","TEXT NOT NULL DEFAULT ''"),
            ("services_json","TEXT NOT NULL DEFAULT '[]'"),
        ):
            self._ensure_column("freyja_markets",column,definition)
        self.execute("""CREATE TABLE IF NOT EXISTS freyja_market_commodities
        (market_id INTEGER NOT NULL, commodity TEXT NOT NULL, buy_price INTEGER NOT NULL DEFAULT 0,
        sell_price INTEGER NOT NULL DEFAULT 0, mean_price INTEGER NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0, demand INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL, PRIMARY KEY(market_id,commodity))""")
        self.execute("""CREATE INDEX IF NOT EXISTS idx_freyja_commodity_name
        ON freyja_market_commodities(commodity)""")
        self.execute("""CREATE INDEX IF NOT EXISTS idx_freyja_market_power
        ON freyja_markets(power_name)""")
        self.execute("""CREATE TABLE IF NOT EXISTS eddn_outbox
        (message_key TEXT PRIMARY KEY, event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
        created_at TEXT NOT NULL, sent_at TEXT, last_error TEXT NOT NULL DEFAULT '')""")
        self.execute("""CREATE INDEX IF NOT EXISTS idx_eddn_outbox_due
        ON eddn_outbox(status,next_attempt_at)""")
        self.execute("""CREATE TABLE IF NOT EXISTS edsm_outbox
        (event_key TEXT PRIMARY KEY, event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL, game_version TEXT NOT NULL,
        game_build TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
        created_at TEXT NOT NULL, sent_at TEXT, last_error TEXT NOT NULL DEFAULT '')""")
        self.execute("""CREATE INDEX IF NOT EXISTS idx_edsm_outbox_due
        ON edsm_outbox(status,next_attempt_at)""")
        self.execute("""CREATE TABLE IF NOT EXISTS inara_outbox
        (event_key TEXT PRIMARY KEY, event_name TEXT NOT NULL,
        payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
        created_at TEXT NOT NULL, sent_at TEXT, last_error TEXT NOT NULL DEFAULT '')""")
        self.execute("""CREATE INDEX IF NOT EXISTS idx_inara_outbox_due
        ON inara_outbox(status,next_attempt_at)""")

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_command_memory
            (
                commander_key TEXT NOT NULL,
                normalized_phrase TEXT NOT NULL,
                original_phrase TEXT NOT NULL,
                intent TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                use_count INTEGER NOT NULL DEFAULT 1,
                confirmation_count INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'adaptive',
                created_at TEXT NOT NULL,
                last_used_at TEXT NOT NULL,
                PRIMARY KEY (commander_key, normalized_phrase)
            )
            """
        )
        self._ensure_column(
            "voice_command_memory", "source",
            "TEXT NOT NULL DEFAULT 'adaptive'",
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_calibration_profiles
            (
                commander_key TEXT PRIMARY KEY,
                consented_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._ensure_column("voice_calibration_profiles", "duration_total", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("voice_calibration_profiles", "rms_total", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("voice_calibration_profiles", "acoustic_samples", "INTEGER NOT NULL DEFAULT 0")

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
                last_arrived_system TEXT NOT NULL DEFAULT '',
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
            "heimdall_planned_routes",
            "last_arrived_system",
            "TEXT NOT NULL DEFAULT ''",
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
