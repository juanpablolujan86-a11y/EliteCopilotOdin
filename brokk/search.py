"""Búsqueda comunitaria de zonas mineras conocidas mediante Spansh."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import requests


class MiningSearchError(RuntimeError):
    pass


MINERAL_ALIASES = {
    "platino": "Platinum", "painita": "Painite", "tritio": "Tritium",
    "osmio": "Osmium", "monacita": "Monazite",
    "alejandrita": "Alexandrite", "musgravita": "Musgravite",
    "benitoita": "Benitoite", "benitoíta": "Benitoite",
    "bromelita": "Bromellite", "serendibita": "Serendibite",
    "ópalo del vacío": "Void Opal", "ópalos del vacío": "Void Opal",
    "diamantes de baja temperatura": "Low Temperature Diamonds",
}


def normalize_mineral_query(mineral: str) -> str:
    normalized = " ".join(str(mineral).split())
    return MINERAL_ALIASES.get(normalized.casefold(), normalized)


@dataclass(frozen=True, slots=True)
class MiningLocation:
    mineral: str
    system: str
    body: str
    ring: str
    ring_type: str
    reserve_level: str
    hotspot_count: int
    distance_ly: float
    distance_ls: float
    updated_at: str
    provider: str = "Spansh"

    def to_dict(self) -> dict:
        return asdict(self)


class SpanshMiningSearchClient:
    URL = "https://spansh.co.uk/api/bodies/search"

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def locations(
        self, origin: str, mineral: str, *, max_distance_ly: float = 900.0,
    ) -> tuple[MiningLocation, ...]:
        origin = " ".join(origin.split())
        mineral = " ".join(mineral.split())
        if not origin or not mineral:
            raise ValueError("La ubicación y el mineral son obligatorios.")
        payload = {
            "filters": {
                "ring_signals": [{
                    "comparison": "<=>", "count": [1, 1000], "name": mineral,
                }],
                "reserve_level": {"value": ["Pristine", "Major"]},
                "distance": {"min": 0, "max": float(max_distance_ly)},
            },
            "sort": [{"distance": {"direction": "asc"}}],
            "size": 100,
            "page": 0,
            "reference_system": origin,
        }
        try:
            response = self.session.post(
                self.URL, json=payload, timeout=45,
                headers={"User-Agent": "ODIN Elite Copilot"},
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError, TypeError) as error:
            raise MiningSearchError(
                "No se pudieron consultar zonas mineras comunitarias."
            ) from error
        return self._records(data, mineral, max_distance_ly)

    @staticmethod
    def _records(payload: dict, mineral: str, maximum: float):
        records = []
        for body in payload.get("results", ()) or ():
            distance = float(body.get("distance", 0) or 0)
            if distance > maximum:
                continue
            for ring in body.get("rings", ()) or ():
                count = _signal_count(ring.get("signals"), mineral)
                if count <= 0:
                    continue
                records.append(MiningLocation(
                    mineral=mineral,
                    system=str(body.get("system_name", "") or ""),
                    body=str(body.get("name", "") or ""),
                    ring=str(ring.get("name", "") or ""),
                    ring_type=str(ring.get("type", "") or ""),
                    reserve_level=str(body.get("reserve_level", "") or ""),
                    hotspot_count=count,
                    distance_ly=distance,
                    distance_ls=float(body.get("distance_to_arrival", 0) or 0),
                    updated_at=str(
                        body.get("signals_updated_at", body.get("updated_at", "")) or ""
                    ),
                ))
        return tuple(sorted(records, key=lambda item: (
            item.distance_ly, -item.hotspot_count, item.distance_ls,
        )))


def select_mining_distance_tiers(
    locations: tuple[MiningLocation, ...],
) -> dict[str, MiningLocation]:
    """Elige una zona conocida para alcance corto, medio y largo."""

    ranges = {
        "short": (0.0, 100.0),
        "medium": (100.0, 300.0),
        "long": (300.0, 900.0),
    }
    selected = {}
    for tier, (minimum, maximum) in ranges.items():
        candidates = [
            item for item in locations
            if minimum <= item.distance_ly <= maximum
        ]
        if candidates:
            selected[tier] = max(candidates, key=lambda item: (
                item.reserve_level.casefold() == "pristine",
                item.hotspot_count,
                -item.distance_ly,
                -item.distance_ls,
            ))
    return selected


def _signal_count(signals, mineral: str) -> int:
    if isinstance(signals, dict):
        for name, value in signals.items():
            if str(name).casefold() == mineral.casefold():
                return int(value or 0)
        return 0
    for signal in signals or ():
        if str(signal.get("name", "")).casefold() == mineral.casefold():
            return int(signal.get("count", 0) or 0)
    return 0
