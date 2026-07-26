"""
ODIN - Orbital Data Intelligence Nexus

journal_reader.py

Responsabilidad:
- Localizar el Journal activo de Elite Dangerous.
- Leer eventos del Journal.

Autor:
Proyecto ODIN
"""

from pathlib import Path
import json


class JournalReader:
    """
    Localiza y lee el Journal activo.
    """

    def __init__(self, journal_folder: Path):

        self.journal_folder = journal_folder

    def latest_file(self) -> Path | None:
        """
        Devuelve el Journal más recientemente modificado.
        """

        journals = list(self.journal_folder.glob("Journal.*.log"))

        if not journals:
            return None

        # Elegimos el archivo con la fecha de modificación más reciente
        latest = max(
            journals,
            key=lambda file: file.stat().st_mtime
        )

        return latest

    def last_event(self) -> dict | None:
        """
        Devuelve el último evento registrado en el Journal.
        """

        journal = self.latest_file()

        if journal is None:
            return None

        with journal.open(
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            lines = file.readlines()

        if not lines:
            return None

        return json.loads(lines[-1])