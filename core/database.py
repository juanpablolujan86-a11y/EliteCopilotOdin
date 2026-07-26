"""
ODIN - Orbital Data Intelligence Nexus

database.py

Administrador de la base de datos SQLite.

Responsabilidades:
- Conectarse a la base de datos.
- Crear las tablas si no existen.
- Ejecutar consultas.
- Ejecutar inserciones, actualizaciones y eliminaciones.
"""

from pathlib import Path
import sqlite3
from sqlite3 import Connection


class DatabaseManager:
    """
    Gestiona la conexión con SQLite y la creación
    automática de la base de datos.
    """

    def __init__(self, project_root: Path):

        self.database_folder = project_root / "database"

        self.database_folder.mkdir(exist_ok=True)

        self.database_file = self.database_folder / "odin.db"

        self.connection: Connection | None = None

    def connect(self) -> None:
        """
        Abre la conexión con SQLite.
        """

        if self.connection is None:

            self.connection = sqlite3.connect(self.database_file)

            self.connection.row_factory = sqlite3.Row

    def disconnect(self) -> None:
        """
        Cierra la conexión.
        """

        if self.connection is not None:

            self.connection.close()

            self.connection = None

    def execute(self, sql: str, parameters: tuple = ()) -> None:
        """
        Ejecuta INSERT, UPDATE o DELETE.
        """

        cursor = self.connection.cursor()

        cursor.execute(sql, parameters)

        self.connection.commit()

    def query(self, sql: str, parameters: tuple = ()) -> list:
        """
        Ejecuta un SELECT.
        """

        cursor = self.connection.cursor()

        cursor.execute(sql, parameters)

        return cursor.fetchall()

    def create_tables(self) -> None:
        """
        Crea las tablas principales de ODIN.
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