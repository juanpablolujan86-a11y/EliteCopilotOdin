"""Captura local optativa del Journal para EDSM."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from services.edsm_outbox import EDSMOutbox


class EDSMJournalPipeline:
    def __init__(self, outbox: EDSMOutbox, discarded=None) -> None:
        self.outbox = outbox
        self.discarded = discarded or frozenset()
        self.game_version = ""
        self.game_build = ""
        self.logger = logging.getLogger("odin.edsm")

    def bootstrap_journal(self, journal: Path) -> None:
        fileheader = None
        load_game = None
        try:
            with journal.open("r", encoding="utf-8", errors="ignore") as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if event.get("event") == "Fileheader" and fileheader is None:
                        fileheader = event
                    elif event.get("event") == "LoadGame":
                        load_game = event
        except OSError:
            return
        self._remember_version(fileheader or {})
        self._remember_version(load_game or {})

    def capture(self, event: dict) -> bool:
        kind = event.get("event")
        if kind == "Fileheader":
            self._remember_version(event)
            return False
        if kind == "LoadGame":
            self._remember_version(event)
        if kind in self.discarded:
            return False
        if not self.game_version or not self.game_build:
            return False
        try:
            return self.outbox.enqueue(
                event, game_version=self.game_version,
                game_build=self.game_build,
            )
        except (sqlite3.Error, OSError, ValueError):
            self.logger.exception("No se pudo conservar un evento para EDSM")
            return False

    def _remember_version(self, event: dict) -> None:
        if event.get("gameversion") is not None:
            self.game_version = str(event["gameversion"])
        if event.get("build") is not None:
            self.game_build = str(event["build"])
