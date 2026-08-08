"""
ODIN - Orbital Data Intelligence Nexus

CommanderState

Estado vivo del comandante durante la sesión.
"""

from dataclasses import dataclass


@dataclass
class CommanderState:
    commander_name: str = ""
    fid: str = ""
    credits: int = 0
    loan: int = 0
    current_wealth: int = 0

    ship_name: str = ""
    ship_ident: str = ""
    ship_type_localised: str = ""
    game_version: str = ""

    current_system: str = ""
    system_address: int = 0
    current_body: str = ""

    fuel_level: float = 0.0
    fuel_capacity: float = 0.0

    population: int = 0

    star_position: tuple[float, float, float] | None = None
    galactic_region_id: int | None = None
    galactic_region_name: str = ""
    system_stars: list[dict] | None = None
    system_body_types: list[str] | None = None

    docked: bool = False
    landed: bool = False
    supercruise: bool = False
    in_fsd: bool = False

    game_mode: str = ""
    session_start: str = ""
    last_jump: str = ""

    expected_body_count: int = 0
    discovered_body_count: int = 0
    mapped_body_count: int = 0
    biology_signal_count: int = 0
    organic_sample_count: int = 0

    last_scanned_body: str = ""

    def __post_init__(self) -> None:
        if self.system_stars is None:
            self.system_stars = []
        if self.system_body_types is None:
            self.system_body_types = []
