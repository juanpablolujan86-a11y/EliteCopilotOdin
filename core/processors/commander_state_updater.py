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

    def handle_profile_event(self, event: dict) -> None:
        """Actualiza identidad, saldo y nave usando valores oficiales."""

        state = self.commander_state
        name = event.get("Commander") or event.get("Name")
        if name:
            state.commander_name = str(name)
        if event.get("FID"):
            state.fid = str(event["FID"])
        if event.get("Credits") is not None:
            state.credits = int(event["Credits"])
        if event.get("Loan") is not None:
            state.loan = int(event["Loan"])
        bank = event.get("Bank_Account", {})
        if bank.get("Current_Wealth") is not None:
            state.current_wealth = int(bank["Current_Wealth"])

        if event.get("Ship"):
            state.ship_name = str(event.get("ShipName", state.ship_name))
            state.ship_ident = str(event.get("ShipIdent", state.ship_ident))
            state.ship_type_localised = str(
                event.get("Ship_Localised", event.get("Ship", state.ship_type_localised))
            )
        elif event.get("UserShipName"):
            state.ship_name = str(event["UserShipName"])
            state.ship_ident = str(event.get("UserShipId", state.ship_ident))
        if event.get("FuelLevel") is not None:
            state.fuel_level = float(event["FuelLevel"])
        capacity = event.get("FuelCapacity")
        if isinstance(capacity, dict):
            state.fuel_capacity = float(capacity.get("Main", state.fuel_capacity) or 0)
        elif capacity is not None:
            state.fuel_capacity = float(capacity)
        if event.get("GameMode"):
            state.game_mode = str(event["GameMode"])
        if event.get("gameversion"):
            state.game_version = str(event["gameversion"])

    def handle_sale(self, event: dict) -> None:
        """Mantiene el saldo aproximado tras ventas confirmadas de expedición."""

        if event.get("Credits") is not None:
            self.commander_state.credits = int(event["Credits"])
            return
        if event.get("event") in {"SellExplorationData", "MultiSellExplorationData"}:
            earned = int(event.get("TotalEarnings", event.get("BaseValue", 0)) or 0)
        elif event.get("event") == "SellOrganicData":
            earned = sum(
                int(item.get("Value", 0) or 0) + int(item.get("Bonus", 0) or 0)
                for item in event.get("BioData", [])
            )
        else:
            earned = 0
        self.commander_state.credits += earned
