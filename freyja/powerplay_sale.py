"""Búsqueda externa de destinos para vender mercancías en Powerplay."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from freyja.market_source import SpanshMarketClient


REINFORCEMENT_STATES = frozenset({"exploited", "fortified", "stronghold"})
COMMODITY_ALIASES = {
    "reliquias de soontill": "soontill relics",
    "reliquia de soontill": "soontill relics",
}


def normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def external_commodity_name(value: str) -> str:
    clean = normalized(value)
    return COMMODITY_ALIASES.get(clean, clean)


@dataclass(frozen=True, slots=True)
class PowerplaySaleDestination:
    commodity: str
    system: str
    station: str
    power: str
    power_state: str
    distance_ly: float
    distance_to_arrival_ls: float
    sell_price: int
    demand: int
    market_updated_at: str
    has_large_pad: bool


class PowerplaySaleFinder:
    def __init__(self, client: SpanshMarketClient | None = None) -> None:
        self.client = client or SpanshMarketClient()

    def find(
        self, commodity: str, power: str, position,
        *, requires_large_pad: bool = False, allow_planetary: bool = True,
        pages: int = 5,
    ) -> PowerplaySaleDestination | None:
        target = external_commodity_name(commodity)
        candidates = []
        for page in range(max(1, pages)):
            records = self.client.stations_near_power(
                position, power, size=100, page=page
            )
            for record in records:
                if not allow_planetary and bool(record.get("is_planetary")):
                    continue
                state = normalized(record.get("system_power_state", ""))
                if state not in REINFORCEMENT_STATES:
                    continue
                large_pad = bool(record.get("has_large_pad"))
                if requires_large_pad and not large_pad:
                    continue
                for item in record.get("market") or ():
                    item_name = external_commodity_name(
                        item.get("commodity", item.get("name", ""))
                    )
                    if item_name != target:
                        continue
                    candidates.append(PowerplaySaleDestination(
                        commodity=str(item.get("commodity") or commodity),
                        system=str(record.get("system_name", "")),
                        station=str(record.get("name", "")),
                        power=power,
                        power_state=str(record.get("system_power_state", "")),
                        distance_ly=float(record.get("distance", 0) or 0),
                        distance_to_arrival_ls=float(
                            record.get("distance_to_arrival", 0) or 0
                        ),
                        sell_price=int(item.get("sell_price", 0) or 0),
                        demand=int(item.get("demand", 0) or 0),
                        market_updated_at=str(record.get("market_updated_at", "")),
                        has_large_pad=large_pad,
                    ))
        if not candidates:
            return None
        return max(candidates, key=self._score)

    @staticmethod
    def _score(destination: PowerplaySaleDestination):
        try:
            updated = datetime.fromisoformat(
                destination.market_updated_at.replace("Z", "+00:00")
            )
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
        except (TypeError, ValueError):
            age_hours = float("inf")
        fresh = age_hours <= 168
        return (fresh, destination.sell_price, -destination.distance_ly)
