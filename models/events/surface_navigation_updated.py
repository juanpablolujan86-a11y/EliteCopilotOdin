"""Actualización de distancia para una recolección exobiológica."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SurfaceNavigationUpdated:
    genus: str
    species: str
    progress: int
    distance_m: float
    required_distance_m: float
    ready_for_sample: bool

