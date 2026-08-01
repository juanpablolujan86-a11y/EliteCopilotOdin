"""
ODIN - Orbital Data Intelligence Nexus

commander_state_updater.py

Actualiza el estado vivo del comandante a partir
de los eventos recibidos desde Elite Dangerous.
"""

from state.commander_state import CommanderState
from mimir.galactic_region import find_region


class CommanderStateUpdater:
    """
    Mantiene actualizado el CommanderState.
    """

    def __init__(self, commander_state: CommanderState) -> None:
        self.commander_state = commander_state

    def handle_fsd_jump(self, event: dict) -> None:
        """
        Actualiza el estado después de un salto FSD.
        """

        self.commander_state.current_system = event.get(
            "StarSystem",
            self.commander_state.current_system,
        )

        self.commander_state.system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        self.commander_state.current_body = event.get(
            "Body",
            self.commander_state.current_body,
        )

        self.commander_state.fuel_level = event.get(
            "FuelLevel",
            self.commander_state.fuel_level,
        )

        self.commander_state.population = event.get(
            "Population",
            self.commander_state.population,
        )

        star_position = event.get("StarPos")
        if isinstance(star_position, list) and len(star_position) == 3:
            self.commander_state.star_position = tuple(star_position)
            region = find_region(*self.commander_state.star_position)
            self.commander_state.galactic_region_id = (
                region[0] if region else None
            )
            self.commander_state.galactic_region_name = (
                region[1] if region else ""
            )

        self.commander_state.system_stars = [
            {
                "type": event.get("StarClass", ""),
                "luminosity": "",
            }
        ]
        self.commander_state.system_body_types = []

        self.commander_state.last_jump = event.get(
            "timestamp",
            self.commander_state.last_jump,
        )

        self.commander_state.in_fsd = False
        self.commander_state.supercruise = False

        print(
            "Estado ODIN           : "
            f"Sistema actual {self.commander_state.current_system}"
        )

    def restore_context(self, context: dict) -> None:
        """Restaura el estado mínimo al iniciar ODIN a mitad de sesión."""

        self.commander_state.current_system = context.get(
            "StarSystem",
            self.commander_state.current_system,
        )
        self.commander_state.system_address = context.get(
            "SystemAddress",
            self.commander_state.system_address,
        )
        self.commander_state.current_body = context.get(
            "Body",
            self.commander_state.current_body,
        )
        self.commander_state.fuel_level = context.get(
            "FuelLevel",
            self.commander_state.fuel_level,
        )
        self.commander_state.population = context.get(
            "Population",
            self.commander_state.population,
        )
        star_position = context.get("StarPos")
        if isinstance(star_position, list) and len(star_position) == 3:
            self.commander_state.star_position = tuple(star_position)
            region = find_region(*self.commander_state.star_position)
            self.commander_state.galactic_region_id = (
                region[0] if region else None
            )
            self.commander_state.galactic_region_name = (
                region[1] if region else ""
            )
        star_class = context.get("StarClass")
        if star_class:
            self.commander_state.system_stars = [
                {"type": star_class, "luminosity": ""}
            ]
        self.commander_state.last_jump = context.get(
            "timestamp",
            self.commander_state.last_jump,
        )
