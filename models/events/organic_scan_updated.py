"""Evento interno con el progreso de una muestra exobiológica."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrganicScanUpdated:
    body_id: int | None
    genus: str
    species: str
    variant: str
    scan_type: str
    progress: int
    completed: bool
    was_logged: bool | None
    required_distance_m: float | None = None
