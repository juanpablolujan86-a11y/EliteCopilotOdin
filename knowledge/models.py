"""
knowledge.models

Modelos de datos utilizados por la Biblioteca del Conocimiento de ODIN.
"""

from dataclasses import dataclass, field


@dataclass
class KnowledgeSource:
    """
    Fuente utilizada para construir una parte del conocimiento.
    """

    name: str
    reference: str = ""
    last_verified: str = ""


@dataclass
class DomainCatalog:
    """
    Describe un dominio de la Biblioteca del Conocimiento.
    """

    domain: str
    name: str
    version: str
    status: str

    sources: list[KnowledgeSource] = field(
        default_factory=list
    )


@dataclass
class HabitatProfile:
    """
    Condiciones ambientales compatibles con una especie.
    """

    planet_classes: list[str] = field(
        default_factory=list
    )

    atmospheres: list[str] = field(
        default_factory=list
    )

    volcanism: list[str] = field(
        default_factory=list
    )

    minimum_temperature: float | None = None
    maximum_temperature: float | None = None

    minimum_gravity: float | None = None
    maximum_gravity: float | None = None


@dataclass
class SpeciesProfile:
    """
    Perfil científico de una especie exobiológica.
    """

    identifier: str

    genus: str
    species: str
    variant: str = ""

    base_value: int = 0
    colony_range_m: int = 0

    rarity: str = "unknown"

    habitat: HabitatProfile = field(
        default_factory=HabitatProfile
    )

    sources: list[KnowledgeSource] = field(
        default_factory=list
    )