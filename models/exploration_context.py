"""
ODIN
Orbital Data Intelligence Nexus

Exploration Context

Representa todo el conocimiento que ODIN posee
sobre un sistema estelar en un instante determinado.
"""

from dataclasses import dataclass, field


@dataclass
class ExplorationContext:
    """
    Estado completo de un sistema.
    """

    system_name: str = ""

    system_address: int = 0

    population: int = 0

    first_visit: bool = False

    edsm_found: bool = False

    edsm_data: dict = field(default_factory=dict)

    bodies: list = field(default_factory=list)

    biology: list = field(default_factory=list)

    recommendations: list = field(default_factory=list)