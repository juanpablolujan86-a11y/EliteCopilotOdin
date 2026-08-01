"""
models.prediction

Resultado de una predicción realizada por MÍMIR.
"""

from dataclasses import dataclass

from models.species import Species


@dataclass(slots=True)
class Prediction:
    """
    Representa una predicción para una especie.
    """

    species: Species

    score: int

    rule_id: str

    matches: list[str]

    variants: tuple[str, ...] = ()
