"""Valoración comunitaria conservadora de carga minera mediante Spansh."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from urllib.parse import quote

import requests


class MiningValuationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MiningSaleDestination:
    commodity: str
    system: str
    station: str
    station_type: str
    unit_price: int
    demand: int
    quantity: int
    estimated_value: int
    distance_ly: float
    distance_ls: float
    updated_at: str
    carrier: bool
    large_pad: bool
    provider: str = "Spansh"

    def to_dict(self) -> dict:
        return asdict(self)


class SpanshMiningValuationClient:
    BASE_URL = "https://spansh.co.uk/api"

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def destinations(
        self, origin: str, commodity: str, quantity: int
    ) -> tuple[MiningSaleDestination, ...]:
        url = (
            f"{self.BASE_URL}/commodity/sell/{quote(origin, safe='')}/"
            f"{quote(commodity, safe='')}/{max(1, int(quantity))}"
        )
        try:
            response = self.session.get(
                url, timeout=45, headers={"User-Agent": "ODIN Elite Copilot"}
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError) as error:
            raise MiningValuationError(
                "No se pudieron consultar precios mineros comunitarios."
            ) from error

        return self._records(payload, commodity, quantity)

    def global_destinations(
        self, commodity: str, quantity: int,
        coordinates: tuple[float, float, float] | None = None,
    ) -> tuple[MiningSaleDestination, ...]:
        payload = {
            "filters": {"market": [{
                "name": commodity,
                "sell_price": {"comparison": "<=>", "value": [1, 10_000_000]},
                "demand": {
                    "comparison": "<=>",
                    "value": [max(1, quantity * 5), 1_000_000_000],
                },
            }]},
            "sort": [{"market_sell_price": [
                {"name": commodity, "direction": "desc"}
            ]}],
            "size": 100,
            "page": 0,
        }
        try:
            response = self.session.post(
                f"{self.BASE_URL}/stations/search", json=payload, timeout=45,
                headers={"User-Agent": "ODIN Elite Copilot"},
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError, TypeError) as error:
            raise MiningValuationError(
                "No se pudo consultar la valoración minera global."
            ) from error
        return self._records(result, commodity, quantity, coordinates)

    @staticmethod
    def _records(
        payload: dict, commodity: str, quantity: int,
        origin: tuple[float, float, float] | None = None,
    ):
        result = []
        for station in payload.get("results", ()) or ():
            market = next((
                item for item in station.get("market", ()) or ()
                if str(item.get("commodity", "")).casefold()
                == commodity.casefold()
            ), None)
            if not market:
                continue
            demand = max(0, int(market.get("demand", 0) or 0))
            price = max(0, int(market.get("sell_price", 0) or 0))
            if price <= 0 or demand < quantity:
                continue
            station_type = str(station.get("type", "") or "")
            carrier = "carrier" in station_type.casefold()
            distance_ly = float(station.get("distance", 0) or 0)
            if origin and all(station.get(key) is not None for key in (
                "system_x", "system_y", "system_z"
            )):
                distance_ly = math.dist(origin, (
                    float(station["system_x"]),
                    float(station["system_y"]),
                    float(station["system_z"]),
                ))
            result.append(MiningSaleDestination(
                commodity=commodity,
                system=str(station.get("system_name", "") or ""),
                station=str(station.get("name", "") or ""),
                station_type=station_type,
                unit_price=price,
                demand=demand,
                quantity=quantity,
                estimated_value=price * quantity,
                distance_ly=distance_ly,
                distance_ls=float(station.get("distance_to_arrival", 0) or 0),
                updated_at=str(station.get("market_updated_at", "") or ""),
                carrier=carrier,
                large_pad=bool(station.get("has_large_pad")),
            ))
        return tuple(sorted(
            result,
            key=lambda item: (
                item.carrier,
                not item.large_pad,
                -item.unit_price,
                item.distance_ly,
                item.distance_ls,
            ),
        ))


def select_recommended_destination(
    destinations: tuple[MiningSaleDestination, ...],
    *, now: datetime | None = None,
) -> MiningSaleDestination | None:
    """Prioriza un precio alcanzable para la carga completa y nave grande."""

    current = now or datetime.now(timezone.utc)
    permanent = [item for item in destinations if not item.carrier and item.large_pad]
    safe = [
        item for item in permanent
        if item.demand >= item.quantity * 5
        and _age_hours(item.updated_at, current) <= 12
    ]
    candidates = safe or permanent
    return max(
        candidates,
        key=lambda item: (item.estimated_value, -item.distance_ly, -item.distance_ls),
        default=None,
    )


def select_permanent_options(
    destinations: tuple[MiningSaleDestination, ...],
    *, limit: int = 3, max_distance_ly: float = 900.0,
    now: datetime | None = None,
) -> tuple[MiningSaleDestination, ...]:
    """Devuelve alternativas seguras, permanentes y dentro del alcance indicado."""

    current = now or datetime.now(timezone.utc)
    candidates = [
        item for item in destinations
        if not item.carrier
        and item.large_pad
        and item.distance_ly <= max_distance_ly
        and item.demand >= item.quantity * 5
        and _age_hours(item.updated_at, current) <= 12
    ]
    candidates.sort(key=lambda item: (
        -item.estimated_value, item.distance_ly, item.distance_ls
    ))
    return tuple(candidates[:max(0, int(limit))])


def select_distance_tiers(
    destinations: tuple[MiningSaleDestination, ...],
    *, now: datetime | None = None,
) -> dict[str, MiningSaleDestination]:
    """Elige el mejor destino seguro de corto, medio y largo alcance."""

    current = now or datetime.now(timezone.utc)
    tiers = {
        "short": (0.0, 100.0),
        "medium": (100.0, 300.0),
        "long": (300.0, 900.0),
    }
    selected = {}
    for name, (minimum, maximum) in tiers.items():
        candidates = [
            item for item in destinations
            if not item.carrier
            and item.large_pad
            and minimum <= item.distance_ly <= maximum
            and item.demand >= item.quantity * 5
            and _age_hours(item.updated_at, current) <= 12
        ]
        if candidates:
            selected[name] = max(candidates, key=lambda item: (
                item.estimated_value, -item.distance_ly, -item.distance_ls
            ))
    return selected


def destination_risk(item: MiningSaleDestination) -> str:
    ratio = item.quantity / item.demand if item.demand else 1.0
    if item.carrier:
        return "ALTO · carrier"
    if ratio <= 0.20:
        return "BAJO"
    if ratio <= 0.25:
        return "MEDIO"
    return "ALTO · posible penalización por volumen"


def _age_hours(value: str, now: datetime) -> float:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (now - stamp.astimezone(timezone.utc)).total_seconds() / 3600)
    except (TypeError, ValueError):
        return float("inf")
