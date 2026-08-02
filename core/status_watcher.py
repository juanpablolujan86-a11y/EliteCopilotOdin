"""Lee los cambios de Status.json publicados por Elite Dangerous."""

from __future__ import annotations

import json
from pathlib import Path


class StatusWatcher:
    def __init__(self, status_file: Path) -> None:
        self.status_file = status_file
        self._last_mtime_ns = -1

    def poll(self) -> dict | None:
        try:
            mtime_ns = self.status_file.stat().st_mtime_ns
            if mtime_ns == self._last_mtime_ns:
                return None
            status = json.loads(self.status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        self._last_mtime_ns = mtime_ns
        return status

