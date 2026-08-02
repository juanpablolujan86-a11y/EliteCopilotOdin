"""Seguimiento de distancia entre muestras exobiológicas."""

from __future__ import annotations

import math

from knowledge.external.explodata.genus_data import data as GENUS_DATA
from models.events.surface_navigation_updated import SurfaceNavigationUpdated


class SurfaceNavigationTracker:
    """Conserva muestras activas y calcula distancia geodésica superficial."""

    def __init__(self) -> None:
        self.latitude: float | None = None
        self.longitude: float | None = None
        self.planet_radius_m: float | None = None
        self.genus = ""
        self.species = ""
        self.progress = 0
        self.sample_locations: list[tuple[float, float]] = []
        self._last_distance_band: int | None = None
        self._last_ready: bool | None = None

    def update_status(self, status: dict) -> SurfaceNavigationUpdated | None:
        latitude = status.get("Latitude")
        longitude = status.get("Longitude")
        radius = status.get("PlanetRadius")
        if latitude is None or longitude is None or not radius:
            self.latitude = self.longitude = self.planet_radius_m = None
            return None

        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.planet_radius_m = float(radius)
        return self._distance_update(only_when_changed=True)

    def record_sample(self, event: dict) -> SurfaceNavigationUpdated | None:
        scan_type = str(event.get("ScanType", ""))
        progress = {"Log": 1, "Sample": 2, "Analyse": 3}.get(scan_type, 0)
        if not progress:
            return None

        genus = str(event.get("Genus", event.get("Genus_Localised", "")))
        species = str(event.get("Species", event.get("Species_Localised", "")))

        if progress == 1 or genus != self.genus or species != self.species:
            self.sample_locations.clear()

        self.genus = genus
        self.species = species
        self.progress = progress
        self._last_distance_band = None
        self._last_ready = None

        if self.latitude is not None and self.longitude is not None:
            location = (self.latitude, self.longitude)
            if location not in self.sample_locations:
                self.sample_locations.append(location)

        if progress >= 3:
            return None
        return self._distance_update(only_when_changed=False)

    def _distance_update(
        self,
        *,
        only_when_changed: bool,
    ) -> SurfaceNavigationUpdated | None:
        if (
            self.progress not in (1, 2)
            or self.latitude is None
            or self.longitude is None
            or self.planet_radius_m is None
            or not self.sample_locations
        ):
            return None

        current = (self.latitude, self.longitude)
        distance = min(
            self._surface_distance(location, current, self.planet_radius_m)
            for location in self.sample_locations
        )
        required = self.required_distance(self.genus)
        ready = distance >= required
        band = int(distance // 25)
        if only_when_changed:
            # Una vez fuera del radio válido no seguimos aumentando el
            # contador. Sólo volvemos a informar si el comandante regresa
            # por debajo de la distancia mínima.
            if ready and self._last_ready is True:
                return None
            if band == self._last_distance_band and ready == self._last_ready:
                return None

        self._last_distance_band = band
        self._last_ready = ready
        return SurfaceNavigationUpdated(
            genus=self.genus,
            species=self.species,
            progress=self.progress,
            distance_m=min(distance, required),
            required_distance_m=required,
            ready_for_sample=ready,
        )

    @staticmethod
    def required_distance(genus: str) -> float:
        return float(GENUS_DATA.get(genus, {}).get("distance", 100))

    @staticmethod
    def _surface_distance(
        first: tuple[float, float],
        second: tuple[float, float],
        radius_m: float,
    ) -> float:
        phi_1 = math.radians(first[0])
        phi_2 = math.radians(second[0])
        delta_phi = math.radians(second[0] - first[0])
        delta_lambda = math.radians(second[1] - first[1])
        value = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2) ** 2
        )
        arc = 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
        return radius_m * arc
