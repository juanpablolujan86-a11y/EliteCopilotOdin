"""Lectura local de constantes FSD mantenidas por EDMarketConnector."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FSDModuleSpec:
    symbol: str
    optimal_mass: float
    max_fuel_per_jump: float
    fuel_multiplier: float
    fuel_power: float
    source: Path


class FSDModuleCatalog:
    def __init__(self, candidates: tuple[Path, ...] | None = None) -> None:
        self.candidates = candidates or self.default_candidates()
        self._loaded_path: Path | None = None
        self._modules: dict = {}

    @staticmethod
    def default_candidates() -> tuple[Path, ...]:
        paths: list[Path] = []
        local = os.environ.get("LOCALAPPDATA")
        if local:
            paths.append(Path(local) / "EDMarketConnector" / "modules.json")
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            paths.append(Path(program_files) / "EDMarketConnector" / "modules.json")
        paths.append(Path.cwd() / "modules.json")
        return tuple(dict.fromkeys(paths))

    def resolve(self, symbol: str) -> FSDModuleSpec | None:
        self._load()
        key = self._normalize(symbol)
        item = self._modules.get(key)
        if not isinstance(item, dict) or self._loaded_path is None:
            return None
        try:
            return FSDModuleSpec(
                symbol=key,
                optimal_mass=float(item["optmass"]),
                max_fuel_per_jump=float(item["maxfuel"]),
                fuel_multiplier=float(item["fuelmul"]),
                fuel_power=float(item["fuelpower"]),
                source=self._loaded_path,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _load(self) -> None:
        if self._loaded_path is not None:
            return
        for path in self.candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                self._modules = payload
                self._loaded_path = path.resolve()
                return

    @staticmethod
    def _normalize(symbol: str) -> str:
        value = str(symbol).strip().casefold().strip("$").rstrip(";")
        return value[:-5] if value.endswith("_name") else value
