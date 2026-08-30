"""Búsqueda de estaciones compatibles delegada a FREYJA."""

from __future__ import annotations

from freyja.market_source import SpanshMarketClient


class StationFinder:
    def __init__(self, client: SpanshMarketClient | None = None) -> None:
        self.client = client or SpanshMarketClient()

    def nearest(self, coordinates: tuple[float, float, float], *,
                requires_large_pad: bool, allow_planetary: bool = True,
                limit: int = 3) -> tuple[dict, ...]:
        records = self.client.stations_near(
            coordinates, size=100, page=0, require_market=False
        )
        matches = []
        for record in records:
            has_large_pad = bool(record.get("has_large_pad"))
            is_planetary = bool(record.get("is_planetary"))
            if requires_large_pad and not has_large_pad:
                continue
            if not allow_planetary and is_planetary:
                continue
            matches.append({
                "system": str(record.get("system_name", record.get("systemName", ""))),
                "station": str(record.get("name", record.get("station_name", ""))),
                "distance_ly": float(record.get("distance", 0) or 0),
                "distance_ls": float(record.get("distance_to_arrival", 0) or 0),
                "station_type": str(record.get("type", "") or ""),
                "large_pad": has_large_pad, "planetary": is_planetary,
                "services": tuple(record.get("services", ()) or ()),
                "provider": "Spansh",
            })
        matches.sort(key=lambda item: (item["distance_ly"], item["distance_ls"]))
        return tuple(matches[: max(1, int(limit))])

    def in_system(
        self, coordinates: tuple[float, float, float], system: str, *,
        requires_large_pad: bool = False, allow_planetary: bool = True,
        limit: int = 20,
    ) -> tuple[dict, ...]:
        wanted = " ".join(str(system or "").casefold().split())
        if not wanted:
            return ()
        records = self.client.stations_near(
            coordinates, size=100, page=0, require_market=False
        )
        matches = []
        for record in records:
            record_system = str(
                record.get("system_name", record.get("systemName", ""))
            )
            if " ".join(record_system.casefold().split()) != wanted:
                continue
            has_large_pad = bool(record.get("has_large_pad"))
            is_planetary = bool(record.get("is_planetary"))
            if requires_large_pad and not has_large_pad:
                continue
            if not allow_planetary and is_planetary:
                continue
            matches.append({
                "system": record_system,
                "station": str(record.get("name", record.get("station_name", ""))),
                "distance_ly": float(record.get("distance", 0) or 0),
                "distance_ls": float(record.get("distance_to_arrival", 0) or 0),
                "station_type": str(record.get("type", "") or ""),
                "large_pad": has_large_pad, "planetary": is_planetary,
                "services": tuple(record.get("services", ()) or ()),
                "provider": "Spansh",
            })
        matches.sort(key=lambda item: item["distance_ls"])
        return tuple(matches[: max(1, int(limit))])
