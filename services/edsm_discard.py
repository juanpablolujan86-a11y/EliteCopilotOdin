"""Lista dinámica y persistente de eventos que EDSM no procesa."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import requests


class EDSMDiscardRegistry:
    ENDPOINT = "https://www.edsm.net/api-journal-v1/discard"
    CACHE_FILENAME = "edsm_discard_events.json"

    def __init__(self, data_root: Path, *, session=None) -> None:
        self.cache_path = Path(data_root) / self.CACHE_FILENAME
        self.session = session or requests.Session()
        self.logger = logging.getLogger("odin.edsm")
        self._lock = threading.Lock()
        self._events = self._load_cache()

    def __contains__(self, event_type: object) -> bool:
        with self._lock:
            return event_type in self._events

    def snapshot(self) -> frozenset[str]:
        with self._lock:
            return self._events

    def refresh(self) -> bool:
        try:
            response = self.session.get(
                self.ENDPOINT,
                headers={"Accept": "application/json", "User-Agent": "ODIN"},
                timeout=(5, 20),
            )
            response.raise_for_status()
            payload = response.json()
            events = self._validated(payload)
            if not events:
                raise ValueError("EDSM devolvió una lista de descartes vacía")
            self._save_cache(events)
        except (requests.RequestException, OSError, TypeError, ValueError):
            self.logger.warning(
                "No se pudo actualizar la lista de descartes EDSM; se conserva la caché",
                exc_info=True,
            )
            return False
        with self._lock:
            self._events = events
        self.logger.info("EDSM_DISCARD_UPDATED | eventos=%s", len(events))
        return True

    def _load_cache(self) -> frozenset[str]:
        try:
            return self._validated(json.loads(self.cache_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return frozenset()

    def _save_cache(self, events: frozenset[str]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(sorted(events), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.cache_path)

    @staticmethod
    def _validated(payload) -> frozenset[str]:
        if not isinstance(payload, list) or not all(
            isinstance(item, str) and item.strip() for item in payload
        ):
            raise ValueError("Lista de descartes EDSM inválida")
        return frozenset(item.strip() for item in payload)
