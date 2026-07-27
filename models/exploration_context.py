"""
ODIN - Orbital Data Intelligence Nexus

ExplorationContext

Representa el conocimiento actual sobre un sistema.
"""

from dataclasses import dataclass, field


@dataclass
class ExplorationContext:
    system_name: str = ""
    system_address: int = 0
    population: int = 0

    first_visit: bool = False

    edsm_found: bool = False
    edsm_data: dict = field(default_factory=dict)

    expected_body_count: int = 0
    discovered_body_count: int = 0

    star_count: int = 0
    planet_count: int = 0
    moon_count: int = 0

    terraformable_count: int = 0
    mapped_count: int = 0

    biology_signal_count: int = 0
    organic_sample_count: int = 0

    all_bodies_found: bool = False

    bodies: list = field(default_factory=list)
    biology: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)