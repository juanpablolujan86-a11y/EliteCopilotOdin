"""Inventario seguro de materiales para inyecciones FSD."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from math import dist
from pathlib import Path
from core.localization import normalize_language, text


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
FSD_INJECTION_MULTIPLIERS = {
    "basic": 1.25,
    "standard": 1.50,
    "premium": 2.00,
}
FSD_INJECTION_LABELS = {
    "basic": "básica",
    "standard": "estándar",
    "premium": "premium",
}


@dataclass(frozen=True, slots=True)
class FSDInjectionAvailability:
    basic: int
    standard: int
    premium: int


@dataclass(frozen=True, slots=True)
class FSDInjectionRecommendation:
    distance_ly: float
    base_range_ly: float
    grade: str | None
    boosted_range_ly: float
    available: bool
    already_reachable: bool
    reachable_with_injection: bool


@dataclass(frozen=True, slots=True)
class RouteInjectionRequirement:
    source_system: str
    destination_system: str
    recommendation: FSDInjectionRecommendation


@dataclass(frozen=True, slots=True)
class PendingFSDInjectionAuthorization:
    grade: str
    distance_ly: float
    boosted_range_ly: float
    source_system: str
    destination_system: str
    expires_at: float


class FSDInjectionInventory:
    """Conserva únicamente materias primas relevantes para el salto."""

    RELEVANT = frozenset(
        material
        for recipe in FSD_INJECTION_RECIPES.values()
        for material in recipe
    )

    def __init__(self, path: Path, *, clock=time.monotonic, language: str = "es-419") -> None:
        self.path = path
        self.clock = clock
        self.language = normalize_language(language)
        self.materials = self._load()
        self.pending_authorization: PendingFSDInjectionAuthorization | None = None

    def _t(self, key: str, **values) -> str:
        return text(key, self.language, **values)

    def _grade(self, grade: str) -> str:
        return self._t(f"fsd.grade.{grade}")

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
        return self._t("fsd.summary", basic=available.basic,
                       standard=available.standard, premium=available.premium)

    def recommend(
        self, distance_ly: float, base_range_ly: float
    ) -> FSDInjectionRecommendation:
        distance = max(0.0, float(distance_ly))
        base_range = max(0.0, float(base_range_ly))
        if distance <= base_range and base_range > 0:
            return FSDInjectionRecommendation(
                distance, base_range, None, base_range, True, True, True
            )
        availability = self.availability()
        for grade, multiplier in FSD_INJECTION_MULTIPLIERS.items():
            boosted = base_range * multiplier
            if distance <= boosted and base_range > 0:
                count = int(getattr(availability, grade))
                return FSDInjectionRecommendation(
                    distance, base_range, grade, boosted, count > 0, False, True
                )
        return FSDInjectionRecommendation(
            distance, base_range, None, base_range * 2.0,
            False, False, False,
        )

    def recommendation_voice(self, distance_ly: float, base_range_ly: float) -> str:
        recommendation = self.recommend(distance_ly, base_range_ly)
        self.pending_authorization = None
        if recommendation.base_range_ly <= 0:
            return self._t("fsd.no_range")
        if recommendation.already_reachable:
            return self._t("fsd.reachable", distance=f"{recommendation.distance_ly:.1f}")
        if not recommendation.reachable_with_injection:
            return self._t("fsd.beyond_premium", distance=f"{recommendation.distance_ly:.1f}", range=f"{recommendation.boosted_range_ly:.1f}")
        label = self._grade(recommendation.grade)
        if not recommendation.available:
            return self._t("fsd.missing", grade=label)
        self._prepare_authorization(recommendation)
        return self._t("fsd.authorization_request", grade=label,
                       range=f"{recommendation.boosted_range_ly:.1f}")

    def route_requirements(
        self, route, current_index: int | None, base_range_ly: float
    ) -> tuple[RouteInjectionRequirement, ...]:
        """Evalúa tramos convencionales futuros de una ruta del juego."""

        waypoints = tuple(route or ())
        if current_index is None or not 0 <= current_index < len(waypoints):
            return ()
        requirements = []
        for source, destination in zip(
            waypoints[current_index:], waypoints[current_index + 1:]
        ):
            source_class = str(getattr(source, "star_class", "") or "")
            if source_class == "N" or source_class.startswith("D"):
                continue
            source_position = getattr(source, "position", None)
            destination_position = getattr(destination, "position", None)
            if source_position is None or destination_position is None:
                continue
            distance_ly = dist(source_position, destination_position)
            recommendation = self.recommend(distance_ly, base_range_ly)
            if recommendation.already_reachable:
                continue
            requirements.append(RouteInjectionRequirement(
                str(getattr(source, "system", "")),
                str(getattr(destination, "system", "")),
                recommendation,
            ))
        return tuple(requirements)

    def route_voice_summary(
        self, route, current_index: int | None, base_range_ly: float
    ) -> str:
        if base_range_ly <= 0:
            return self._t("fsd.no_range")
        self.pending_authorization = None
        requirements = self.route_requirements(route, current_index, base_range_ly)
        if current_index is None:
            return self._t("fsd.route_mismatch")
        if not requirements:
            return self._t("fsd.route_clear")
        first = requirements[0]
        recommendation = first.recommendation
        if not recommendation.reachable_with_injection:
            detail = self._t("fsd.detail_impossible")
        else:
            label = self._grade(recommendation.grade)
            detail = self._t("fsd.detail_required", grade=label)
            if not recommendation.available:
                detail += self._t("fsd.detail_missing")
            else:
                self._prepare_authorization(
                    recommendation,
                    first.source_system,
                    first.destination_system,
                )
        count_text = self._t("fsd.segment.one") if len(requirements) == 1 else self._t("fsd.segment.many", count=len(requirements))
        return self._t("fsd.route_summary", count=count_text, source=first.source_system,
                       destination=first.destination_system,
                       distance=f"{recommendation.distance_ly:.1f}", detail=detail)

    def authorize_pending_voice(self) -> str:
        pending = self.pending_authorization
        self.pending_authorization = None
        if pending is None:
            return self._t("fsd.no_pending")
        if self.clock() > pending.expires_at:
            return self._t("fsd.expired")
        label = self._grade(pending.grade)
        route_detail = (
            self._t("fsd.route_detail", source=pending.source_system, destination=pending.destination_system)
            if pending.source_system and pending.destination_system else ""
        )
        return self._t("fsd.authorized", grade=label, route=route_detail)

    def _prepare_authorization(
        self,
        recommendation: FSDInjectionRecommendation,
        source_system: str = "",
        destination_system: str = "",
    ) -> None:
        if recommendation.grade is None or not recommendation.available:
            self.pending_authorization = None
            return
        self.pending_authorization = PendingFSDInjectionAuthorization(
            recommendation.grade,
            recommendation.distance_ly,
            recommendation.boosted_range_ly,
            source_system,
            destination_system,
            self.clock() + 60.0,
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
