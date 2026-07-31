"""
models.planet

Modelo de dominio para un planeta analizado por ODIN.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class Planet:
    """
    Representa un planeta con la información
    necesaria para realizar predicciones.
    """

    body_type: str | None = None

    atmosphere: str | None = None

    gravity: float | None = None

    temperature: float | None = None

    pressure: float | None = None

    volcanism: str | None = None

    region: str | None = None

    star_type: str | None = None