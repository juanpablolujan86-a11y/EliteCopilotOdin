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

    def current_system_context(
        self,
        journal: Path | None = None,
    ) -> dict | None:
        """Reconstruye el último sistema conocido sin reproducir eventos."""

        journal_path = journal or self.latest_file()
        if journal_path is None:
            return None

        events = self.current_system_events(journal_path)
        if not events:
            return None

        context: dict = {}
        system_address = events[0].get("SystemAddress")

        for event in events:
            event_address = event.get("SystemAddress")
            if (
                system_address is not None
                and event_address is not None
                and event_address != system_address
            ):
                continue

            system_name = event.get("StarSystem") or event.get("SystemName")
            if system_name:
                context["StarSystem"] = system_name

            if event_address is not None:
                context["SystemAddress"] = event_address

            current_body = event.get("Body") or event.get("BodyName")
            if current_body:
                context["Body"] = current_body

            for key in (
                "FuelLevel",
                "Population",
                "timestamp",
                "StarPos",
                "StarClass",
            ):
                if event.get(key) is not None:
                    context[key] = event[key]

        if not context.get("StarSystem"):
            return None

        return context

    def current_system_events(
        self,
        journal: Path | None = None,
    ) -> list[dict]:
        """Devuelve los eventos desde la última llegada o carga de sistema."""

        journal_path = journal or self.latest_file()
        if journal_path is None:
            return []

        events: list[dict] = []
        anchors = {"FSDJump", "Location", "CarrierJump"}

        with journal_path.open(
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as file:
            for line in file:
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue

                if (
                    event.get("event") in anchors
                    and (event.get("StarSystem") or event.get("SystemName"))
                ):
                    events = [event]
                elif events:
                    events.append(event)

        return events
