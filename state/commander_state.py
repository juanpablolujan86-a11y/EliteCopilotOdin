"""
ODIN
Orbital Data Intelligence Nexus

Commander State

Representa el estado actual del comandante.
"""

from dataclasses import dataclass


@dataclass
class CommanderState:
    """
    Estado actual del comandante.

    Se mantiene en memoria durante toda la sesión.
    """

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