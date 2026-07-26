"""
ODIN
Orbital Data Intelligence Nexus

journal_watcher.py

Observa el Journal de Elite Dangerous y detecta nuevos eventos.
"""

from pathlib import Path
import json
import time


class JournalWatcher:

    def __init__(self, journal_file: Path):

        self.journal_file = journal_file

        self.position = 0

    def start(self):

        """
        Posiciona el lector al final del archivo para comenzar
        a escuchar únicamente los eventos nuevos.
        """

        with open(
            self.journal_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            file.seek(0, 2)

            self.position = file.tell()

    def poll(self):

        """
        Devuelve una lista con todos los eventos nuevos.
        """

        events = []

        with open(
            self.journal_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            file.seek(self.position)

            while True:

                line = file.readline()

                if not line:

                    break

                self.position = file.tell()

                try:

                    event = json.loads(line)

                    events.append(event)

                except Exception:

                    pass

        return events