"""Detección y persistencia de la base principal del comandante."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommanderHomeBase:
    system: str
    station: str
    stored_ships: int
    source: str = "StoredShips"


class HomeBaseManager:
    def __init__(self, data_root: Path) -> None:
        self.path = data_root / "heimdall" / "home_base.json"
        self.current: CommanderHomeBase | None = None

    def load(self) -> CommanderHomeBase | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.current = CommanderHomeBase(**payload)
        except (OSError, ValueError, TypeError):
            self.current = None
        return self.current

    def update_from_stored_ships(self, event: dict) -> CommanderHomeBase | None:
        here_system = str(event.get("StarSystem", "")).strip()
        counts: Counter[str] = Counter()
        if here_system:
            counts[here_system] += len(event.get("ShipsHere", []))
        for ship in event.get("ShipsRemote", []):
            system = str(ship.get("StarSystem", "")).strip()
            if system:
                counts[system] += 1
        if not counts:
            return self.current
        maximum = max(counts.values())
        candidates = {system for system, count in counts.items() if count == maximum}
        system = here_system if here_system in candidates else sorted(candidates)[0]
        station = str(event.get("StationName", "")) if system == here_system else ""
        self.current = CommanderHomeBase(system, station, maximum)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(self.current), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.current
