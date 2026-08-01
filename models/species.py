"""
models.species

Modelo de dominio para una especie biológica.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class Species:
    """
    Representa una especie conocida por la
    Enciclopedia Galáctica.
    """

    id: str

    name: str

    genus: str

    genus_codex_id: str

    value: int = 0
