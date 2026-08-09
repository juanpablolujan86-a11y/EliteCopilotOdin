"""Inventario seguro de materiales para inyecciones FSD."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


FSD_INJECTION_RECIPES = {
    "basic": {"carbon": 1, "vanadium": 1, "germanium": 1},
    "standard": {
        "carbon": 1, "vanadium": 1, "germanium": 1,
        "cadmium": 1, "niobium": 1,
    },
    "premium": {
        "carbon": 1, "germanium": 1, "arsenic": 1,
        "niobium": 1, "yttrium": 1, "polonium": 1,
    },
}


@dataclass(frozen=True, slots=True)
class FSDInjectionAvailability:
    basic: int
    standard: int
    premium: int


class FSDInjectionInventory:
    """Conserva únicamente materias primas relevantes para el salto."""

    RELEVANT = frozenset(
        material
        for recipe in FSD_INJECTION_RECIPES.values()
        for material in recipe
    )

    def __init__(self, path: Path) -> None:
        self.path = path
        self.materials = self._load()

    def handle(self, event: dict) -> None:
        kind = str(event.get("event", ""))
        changed = False
        if kind == "Materials":
            raw = event.get("Raw", ()) or ()
            self.materials = {
                self._name(item.get("Name", "")): max(0, int(item.get("Count", 0) or 0))
                for item in raw
                if self._name(item.get("Name", "")) in self.RELEVANT
            }
            changed = True
        elif kind in {"MaterialCollected", "MaterialDiscarded"}:
            name = self._name(event.get("Name", ""))
            if name in self.RELEVANT:
                amount = max(0, int(event.get("Count", 0) or 0))
                delta = amount if kind == "MaterialCollected" else -amount
                self.materials[name] = max(0, self.materials.get(name, 0) + delta)
                changed = True
        elif kind == "Synthesis":
            for item in event.get("Materials", ()) or ():
                name = self._name(item.get("Name", ""))
                if name not in self.RELEVANT:
                    continue
                amount = max(0, int(item.get("Count", 0) or 0))
                self.materials[name] = max(0, self.materials.get(name, 0) - amount)
                changed = True
        elif kind == "MaterialTrade":
            for key, sign in (("Paid", -1), ("Received", 1)):
                item = event.get(key, {}) or {}
                name = self._name(item.get("Material", ""))
                if name not in self.RELEVANT:
                    continue
                amount = max(0, int(item.get("Quantity", 0) or 0))
                self.materials[name] = max(
                    0, self.materials.get(name, 0) + sign * amount
                )
                changed = True
        elif kind == "MissionCompleted":
            for item in event.get("MaterialsReward", ()) or ():
                name = self._name(item.get("Name", ""))
                if name not in self.RELEVANT:
                    continue
                amount = max(0, int(item.get("Count", 0) or 0))
                self.materials[name] = self.materials.get(name, 0) + amount
                changed = True
        if changed:
            self._save()

    def availability(self) -> FSDInjectionAvailability:
        values = {
            grade: min(
                (self.materials.get(name, 0) // amount for name, amount in recipe.items()),
                default=0,
            )
            for grade, recipe in FSD_INJECTION_RECIPES.items()
        }
        return FSDInjectionAvailability(
            values["basic"], values["standard"], values["premium"]
        )

    def voice_summary(self) -> str:
        available = self.availability()
        return (
            "Puedo preparar "
            f"{available.basic} inyecciones básicas, {available.standard} estándar "
            f"y {available.premium} premium. No utilizaré materiales sin su "
            "autorización, comandante."
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(self.materials, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

    def _load(self) -> dict[str, int]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return {
                    self._name(name): max(0, int(value))
                    for name, value in payload.items()
                    if self._name(name) in self.RELEVANT
                }
        except (FileNotFoundError, OSError, TypeError, ValueError):
            pass
        return {}

    @staticmethod
    def _name(value: str) -> str:
        return str(value).strip("$").removesuffix("_name;").casefold()
