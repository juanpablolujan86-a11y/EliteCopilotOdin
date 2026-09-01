"""Estado persistente y auditable de una operación minera."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MiningSession:
    active: bool = False
    status: str = "idle"
    started_at: str = ""
    ended_at: str = ""
    updated_at: str = ""
    system: str = ""
    body: str = ""
    technique: str = "laser"
    technique_source: str = "commander"
    technique_confirmed: bool = False
    target_mineral: str = ""
    prospected_asteroids: int = 0
    cracked_asteroids: int = 0
    last_prospect: dict = field(default_factory=dict)
    refined: dict[str, int] = field(default_factory=dict)
    produced: dict[str, int] = field(default_factory=dict)
    cargo_inventory: dict[str, int] = field(default_factory=dict)
    cargo_count: int = 0
    limpets: int = 0
    transferred_to_carrier: dict[str, int] = field(default_factory=dict)
    transferred_from_carrier: dict[str, int] = field(default_factory=dict)
    sold: dict[str, int] = field(default_factory=dict)
    discarded: dict[str, int] = field(default_factory=dict)
    engineering_materials: dict[str, int] = field(default_factory=dict)
    sale_revenue: int = 0
    valuation: dict = field(default_factory=dict)
    equipment: dict = field(default_factory=dict)
    announced_fill_levels: list[int] = field(default_factory=list)
    mining_environment: str = "space"
    surface_vehicle: str = ""
    surface_vehicle_active: bool = False
    geological_signals: int = 0
    surface_mining_events: list[dict] = field(default_factory=list)

    @property
    def refined_total(self) -> int:
        return sum(max(0, int(value)) for value in self.refined.values())

    def start(
        self, *, system: str = "", body: str = "", technique: str = "laser",
        technique_source: str = "commander",
    ) -> None:
        if not self.started_at:
            self.started_at = utc_now()
        self.active = True
        self.ended_at = ""
        self.status = "prospecting"
        self.system = system or self.system
        self.body = body or self.body
        self.technique = technique or self.technique
        self.technique_source = technique_source or self.technique_source
        self.touch()

    def pause(self) -> None:
        if not self.active:
            return
        self.active = False
        self.status = "paused"
        self.touch()

    def resume(self) -> None:
        if self.status != "paused":
            return
        self.active = True
        self.status = "extracting" if self.produced else "prospecting"
        self.touch()

    def close(self) -> None:
        self.active = False
        self.status = "completed"
        self.ended_at = utc_now()
        self.touch()

    def touch(self) -> None:
        self.updated_at = utc_now()

    def add_refined(self, commodity: str, count: int = 1) -> None:
        if not commodity or count <= 0:
            return
        self.refined[commodity] = self.refined.get(commodity, 0) + count
        self.produced[commodity] = self.produced.get(commodity, 0) + count
        self.status = "extracting"
        self.touch()

    def remove_refined(self, commodity: str, count: int, destination: dict[str, int]) -> int:
        available = max(0, int(self.refined.get(commodity, 0)))
        removed = min(available, max(0, count))
        if removed:
            remaining = available - removed
            if remaining:
                self.refined[commodity] = remaining
            else:
                self.refined.pop(commodity, None)
            destination[commodity] = destination.get(commodity, 0) + removed
            self.touch()
        return removed

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "MiningSession":
        allowed = cls.__dataclass_fields__.keys()
        loaded = {key: value[key] for key in allowed if key in value}
        if "produced" not in loaded:
            loaded["produced"] = dict(loaded.get("refined", {}))
        return cls(**loaded)


class MiningSessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> MiningSession:
        if not self.path.exists():
            return MiningSession()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return MiningSession.from_dict(value if isinstance(value, dict) else {})
        except (OSError, ValueError, TypeError):
            return MiningSession()

    def save(self, session: MiningSession) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
