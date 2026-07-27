"""
ODIN - Orbital Data Intelligence Nexus

CommanderState

Estado vivo del comandante durante la sesión.
"""

from dataclasses import dataclass


@dataclass
class CommanderState:
    commander_name: str = ""

    ship_name: str = ""
    ship_ident: str = ""

    current_system: str = ""
    system_address: int = 0
    current_body: str = ""

    fuel_level: float = 0.0
    fuel_capacity: float = 0.0

    population: int = 0

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