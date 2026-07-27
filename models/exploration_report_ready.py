"""
ODIN - Orbital Data Intelligence Nexus

ExplorationReportReady
"""

from dataclasses import dataclass, field


@dataclass
class ExplorationReportReady:
    system_name: str

    expected_body_count: int
    discovered_body_count: int

    star_count: int
    planet_count: int
    moon_count: int

    terraformable_count: int
    mapped_count: int

    biology_signal_count: int
    organic_sample_count: int

    all_bodies_found: bool

    priority: str
    recommendation: str

    reasons: list[str] = field(default_factory=list)