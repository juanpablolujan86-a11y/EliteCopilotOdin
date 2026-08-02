"""Contexto persistente de nave, combustible, destino y ruta."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from math import dist
from pathlib import Path

from core.database import DatabaseManager

SCOOPABLE_STARS = frozenset({"O", "B", "A", "F", "G", "K", "M"})


@dataclass(frozen=True, slots=True)
class RouteWaypoint:
    system: str
    address: int | None
    position: tuple[float, float, float] | None
    star_class: str

    @property
    def scoopable(self) -> bool:
        return self.star_class in SCOOPABLE_STARS

    @property
    def neutron(self) -> bool:
        return self.star_class == "N"

    @property
    def white_dwarf(self) -> bool:
        return self.star_class.startswith("D")


@dataclass(frozen=True, slots=True)
class RouteProgress:
    current_index: int | None
    completed_jumps: int
    remaining_jumps: int | None
    remaining_distance_ly: float | None
    next_waypoint: RouteWaypoint | None
    final_waypoint: RouteWaypoint | None
    off_route: bool
    route_complete: bool


@dataclass(frozen=True, slots=True)
class FuelAssessment:
    jumps_available: int | None
    jumps_to_refuel: int | None
    refuel_waypoint: RouteWaypoint | None
    fuel_margin_t: float | None
    unsafe: bool | None
    destination_before_refuel: bool


@dataclass(frozen=True, slots=True)
class HighEnergyAssessment:
    charged: bool
    boost_value: float | None
    last_boost_used: int | None
    cone_exposures_session: int
    boosted_jumps_session: int
    next_neutron: RouteWaypoint | None
    jumps_to_next_neutron: int | None
    remaining_neutrons: int
    remaining_white_dwarfs: int
    fsd_health: float | None


@dataclass(slots=True)
class NavigationContext:
    ship_type: str = ""
    ship_id: int | None = None
    ship_name: str = ""
    ship_ident: str = ""
    max_jump_range: float = 0.0
    fuel_capacity: float = 0.0
    reserve_capacity: float = 0.0
    fuel_main: float = 0.0
    fuel_reservoir: float = 0.0
    fsd_item: str = ""
    fsd_health: float | None = None
    fsd_engineer: str = ""
    fsd_blueprint: str = ""
    fsd_level: int | None = None
    max_fuel_per_jump: float = 0.0
    current_system: str = ""
    current_address: int | None = None
    current_position: tuple[float, float, float] | None = None
    target_system: str = ""
    target_address: int | None = None
    target_star_class: str = ""
    remaining_jumps: int | None = None
    boost_charged: bool = False
    last_boost_value: float | None = None
    last_boost_used: int | None = None
    cone_exposures_session: int = 0
    boosted_jumps_session: int = 0
    last_jump_distance: float | None = None
    last_jump_fuel_used: float | None = None
    route: tuple[RouteWaypoint, ...] = field(default_factory=tuple)

    @property
    def conservative_jumps_available(self) -> int | None:
        if self.max_fuel_per_jump <= 0:
            return None
        return int(self.fuel_main // self.max_fuel_per_jump)

    @property
    def target_is_scoopable(self) -> bool | None:
        if not self.target_star_class:
            return None
        return self.target_star_class in SCOOPABLE_STARS

    def route_progress(self) -> RouteProgress:
        """Calcula el progreso sin asumir que la ruta empieza en el sistema actual."""

        if not self.route:
            return RouteProgress(None, 0, None, None, None, None, False, False)

        current_index = self._current_route_index()
        final = self.route[-1]
        if current_index is None:
            return RouteProgress(None, 0, None, None, None, final, True, False)

        remaining = len(self.route) - current_index - 1
        route_slice = self.route[current_index:]
        distance = 0.0
        for origin, destination in zip(route_slice, route_slice[1:]):
            if origin.position is None or destination.position is None:
                distance = None
                break
            distance += dist(origin.position, destination.position)

        return RouteProgress(
            current_index=current_index,
            completed_jumps=current_index,
            remaining_jumps=remaining,
            remaining_distance_ly=distance,
            next_waypoint=(
                self.route[current_index + 1] if remaining > 0 else None
            ),
            final_waypoint=final,
            off_route=False,
            route_complete=remaining == 0,
        )

    def fuel_assessment(self) -> FuelAssessment:
        """Evalúa de forma conservadora si alcanza hasta el próximo repostaje."""

        progress = self.route_progress()
        available = self.conservative_jumps_available
        if progress.remaining_jumps is None or available is None:
            return FuelAssessment(available, None, None, None, None, False)
        if progress.route_complete:
            return FuelAssessment(available, 0, None, self.fuel_main, False, True)

        assert progress.current_index is not None
        future = self.route[progress.current_index + 1:]
        for jumps, waypoint in enumerate(future, start=1):
            if waypoint.scoopable:
                required_fuel = jumps * self.max_fuel_per_jump
                return FuelAssessment(
                    jumps_available=available,
                    jumps_to_refuel=jumps,
                    refuel_waypoint=waypoint,
                    fuel_margin_t=self.fuel_main - required_fuel,
                    unsafe=available < jumps,
                    destination_before_refuel=False,
                )

        jumps = len(future)
        required_fuel = jumps * self.max_fuel_per_jump
        return FuelAssessment(
            jumps_available=available,
            jumps_to_refuel=jumps,
            refuel_waypoint=None,
            fuel_margin_t=self.fuel_main - required_fuel,
            unsafe=available < jumps,
            destination_before_refuel=True,
        )

    def high_energy_assessment(self) -> HighEnergyAssessment:
        progress = self.route_progress()
        future = (
            self.route[progress.current_index + 1:]
            if progress.current_index is not None else ()
        )
        next_neutron = None
        jumps_to_neutron = None
        for jumps, waypoint in enumerate(future, start=1):
            if waypoint.neutron:
                next_neutron = waypoint
                jumps_to_neutron = jumps
                break
        return HighEnergyAssessment(
            charged=self.boost_charged,
            boost_value=self.last_boost_value,
            last_boost_used=self.last_boost_used,
            cone_exposures_session=self.cone_exposures_session,
            boosted_jumps_session=self.boosted_jumps_session,
            next_neutron=next_neutron,
            jumps_to_next_neutron=jumps_to_neutron,
            remaining_neutrons=sum(waypoint.neutron for waypoint in future),
            remaining_white_dwarfs=sum(waypoint.white_dwarf for waypoint in future),
            fsd_health=self.fsd_health,
        )

    def _current_route_index(self) -> int | None:
        if self.current_address is not None:
            for index, waypoint in enumerate(self.route):
                if waypoint.address == self.current_address:
                    return index
        if self.current_system:
            for index, waypoint in enumerate(self.route):
                if waypoint.system.casefold() == self.current_system.casefold():
                    return index
        return None


class NavigationContextManager:
    """Actualiza el contexto usando eventos oficiales y archivos auxiliares."""

    def __init__(self, database: DatabaseManager, navroute_file: Path) -> None:
        self.database = database
        self.navroute_file = navroute_file
        self.context = NavigationContext()
        self._route_mtime_ns = -1

    def restore(self, journal_file: Path) -> NavigationContext:
        saved = self.database.query(
            "SELECT json FROM heimdall_navigation_state WHERE id=1"
        )
        if saved:
            self._load_saved(json.loads(saved[0]["json"]))

        # Estos contadores pertenecen al Journal/sesión actual. Se reconstruyen
        # para que reiniciar ODIN no duplique exposiciones ni saltos.
        self.context.boost_charged = False
        self.context.last_boost_value = None
        self.context.last_boost_used = None
        self.context.cone_exposures_session = 0
        self.context.boosted_jumps_session = 0

        with journal_file.open("r", encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = event.get("event")
                if name in {
                    "Loadout", "FSDTarget", "FSDJump", "Location",
                    "FuelScoop", "ReservoirReplenished", "JetConeBoost",
                }:
                    # El orden es esencial: un salto posterior debe prevalecer
                    # sobre un repostaje anterior, y viceversa.
                    self.handle_event(event, persist=False)
        self.poll_route(force=True)
        self.persist()
        return self.context

    def handle_event(self, event: dict, *, persist: bool = True) -> None:
        name = event.get("event")
        if name == "Loadout":
            self._handle_loadout(event)
        elif name in {"FSDJump", "Location"}:
            self.context.current_system = event.get("StarSystem", self.context.current_system)
            self.context.current_address = event.get("SystemAddress", self.context.current_address)
            position = event.get("StarPos")
            if isinstance(position, list) and len(position) == 3:
                self.context.current_position = tuple(float(item) for item in position)
            if "FuelLevel" in event:
                self.context.fuel_main = float(event["FuelLevel"])
            if name == "FSDJump":
                self.context.last_jump_distance = event.get("JumpDist")
                self.context.last_jump_fuel_used = event.get("FuelUsed")
                self.context.last_boost_used = event.get("BoostUsed")
                if event.get("BoostUsed"):
                    self.context.boosted_jumps_session += 1
                self.context.boost_charged = False
        elif name == "FSDTarget":
            self.context.target_system = event.get("Name", "")
            self.context.target_address = event.get("SystemAddress")
            self.context.target_star_class = event.get("StarClass", "")
            self.context.remaining_jumps = event.get("RemainingJumpsInRoute")
        elif name == "FuelScoop":
            self.context.fuel_main = float(event.get("Total", self.context.fuel_main))
        elif name == "ReservoirReplenished":
            self.context.fuel_main = float(event.get("FuelMain", self.context.fuel_main))
            self.context.fuel_reservoir = float(
                event.get("FuelReservoir", self.context.fuel_reservoir)
            )
        elif name == "JetConeBoost":
            self.context.boost_charged = True
            self.context.last_boost_value = float(event.get("BoostValue", 0) or 0)
            self.context.cone_exposures_session += 1
        if persist:
            self.persist()

    def update_status(self, status: dict) -> None:
        changed = False
        fuel = status.get("Fuel", {})
        if "FuelMain" in fuel:
            value = float(fuel["FuelMain"])
            changed |= value != self.context.fuel_main
            self.context.fuel_main = value
        if "FuelReservoir" in fuel:
            value = float(fuel["FuelReservoir"])
            changed |= value != self.context.fuel_reservoir
            self.context.fuel_reservoir = value
        destination = status.get("Destination", {})
        if destination.get("Name"):
            name = destination["Name"]
            address = destination.get("System")
            changed |= name != self.context.target_system
            changed |= address != self.context.target_address
            self.context.target_system = name
            self.context.target_address = address
        if changed:
            self.persist()

    def poll_route(self, *, force: bool = False) -> bool:
        try:
            mtime = self.navroute_file.stat().st_mtime_ns
            if not force and mtime == self._route_mtime_ns:
                return False
            payload = json.loads(self.navroute_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        self._route_mtime_ns = mtime
        self.context.route = tuple(
            RouteWaypoint(
                system=item.get("StarSystem", ""),
                address=item.get("SystemAddress"),
                position=(
                    tuple(float(value) for value in item["StarPos"])
                    if len(item.get("StarPos", [])) == 3 else None
                ),
                star_class=item.get("StarClass", ""),
            )
            for item in payload.get("Route", [])
        )
        self.persist()
        return True

    def persist(self) -> None:
        payload = asdict(self.context)
        self.database.execute(
            """
            INSERT INTO heimdall_navigation_state (id, json, updated_at)
            VALUES (1, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at
            """,
            (json.dumps(payload, ensure_ascii=False),),
        )

    def _handle_loadout(self, event: dict) -> None:
        context = self.context
        context.ship_type = event.get("Ship", "")
        context.ship_id = event.get("ShipID")
        context.ship_name = event.get("ShipName", "")
        context.ship_ident = event.get("ShipIdent", "")
        context.max_jump_range = float(event.get("MaxJumpRange", 0) or 0)
        capacity = event.get("FuelCapacity", {})
        context.fuel_capacity = float(capacity.get("Main", 0) or 0)
        context.reserve_capacity = float(capacity.get("Reserve", 0) or 0)
        for module in event.get("Modules", []):
            if module.get("Slot") != "FrameShiftDrive":
                continue
            context.fsd_item = module.get("Item", "")
            context.fsd_health = module.get("Health")
            engineering = module.get("Engineering", {})
            context.fsd_engineer = engineering.get("Engineer", "")
            context.fsd_blueprint = engineering.get("BlueprintName", "")
            context.fsd_level = engineering.get("Level")
            for modifier in engineering.get("Modifiers", []):
                if modifier.get("Label") == "MaxFuelPerJump":
                    context.max_fuel_per_jump = float(modifier.get("Value", 0) or 0)

    def _load_saved(self, payload: dict) -> None:
        route = tuple(
            RouteWaypoint(
                system=item.get("system", ""),
                address=item.get("address"),
                position=(
                    tuple(item["position"])
                    if item.get("position") is not None else None
                ),
                star_class=item.get("star_class", ""),
            )
            for item in payload.pop("route", [])
        )
        for name, value in payload.items():
            if hasattr(self.context, name):
                if name == "current_position" and value is not None:
                    value = tuple(value)
                setattr(self.context, name, value)
        self.context.route = route
