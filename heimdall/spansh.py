"""Planificación de autopistas de neutrones mediante la API pública de Spansh."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from math import ceil
from typing import Callable

import requests

from core.database import DatabaseManager
from heimdall.navigation import NavigationContext
from heimdall.clipboard import write_text


class SpanshRouteError(RuntimeError):
    """La ruta no pudo calcularse o la respuesta no fue válida."""


@dataclass(frozen=True, slots=True)
class ExactWaypoint:
    system: str
    address: int | None
    position: tuple[float, float, float]
    distance_jumped: float
    distance_left: float
    fuel_in_tank: float
    fuel_used: float
    scoopable: bool
    must_refuel: bool
    neutron_star: bool


@dataclass(frozen=True, slots=True)
class ExactRoutePlan:
    job_id: str
    source_system: str
    destination_system: str
    waypoints: tuple[ExactWaypoint, ...]
    provider: str = "Spansh Galaxy Plotter"
    strategy: str = "galaxy_exact"

    @property
    def total_jumps(self) -> int:
        return max(0, len(self.waypoints) - 1)

    @property
    def distance(self) -> float:
        return sum(item.distance_jumped for item in self.waypoints[1:])

    @property
    def next_waypoint(self) -> ExactWaypoint | None:
        return self.waypoints[1] if len(self.waypoints) > 1 else None

    @property
    def actual_total_jumps(self) -> int:
        return self.total_jumps

    @classmethod
    def from_dict(cls, payload: dict) -> "ExactRoutePlan":
        return cls(
            job_id=payload["job_id"],
            source_system=payload["source_system"],
            destination_system=payload["destination_system"],
            waypoints=tuple(
                ExactWaypoint(
                    system=item["system"], address=item.get("address"),
                    position=tuple(item["position"]),
                    distance_jumped=float(item["distance_jumped"]),
                    distance_left=float(item["distance_left"]),
                    fuel_in_tank=float(item["fuel_in_tank"]),
                    fuel_used=float(item["fuel_used"]),
                    scoopable=bool(item["scoopable"]),
                    must_refuel=bool(item["must_refuel"]),
                    neutron_star=bool(item["neutron_star"]),
                )
                for item in payload["waypoints"]
            ),
            provider=payload.get("provider", "Spansh Galaxy Plotter"),
            strategy=payload.get("strategy", "galaxy_exact"),
        )


@dataclass(frozen=True, slots=True)
class SpanshWaypoint:
    system: str
    address: int | None
    position: tuple[float, float, float]
    distance_jumped: float
    distance_left: float
    jumps: int
    neutron_star: bool


@dataclass(frozen=True, slots=True)
class SpanshRoutePlan:
    job_id: str
    source_system: str
    destination_system: str
    jump_range: float
    efficiency: int
    total_jumps: int
    distance: float
    waypoints: tuple[SpanshWaypoint, ...]
    provider: str = "Spansh"
    strategy: str = "neutron_fastest"

    @property
    def next_waypoint(self) -> SpanshWaypoint | None:
        return self.waypoints[1] if len(self.waypoints) > 1 else None

    @property
    def actual_total_jumps(self) -> int:
        """Saltos FSD previstos, incluidos los tramos convencionales."""

        calculated = sum(max(0, waypoint.jumps) for waypoint in self.waypoints[1:])
        return calculated or self.total_jumps

    @property
    def conventional_minimum_jumps(self) -> int | None:
        """Límite inferior teórico; no sustituye una ruta trazada por el juego."""

        if self.jump_range <= 0 or self.distance <= 0:
            return None
        return max(1, ceil(self.distance / self.jump_range))

    @property
    def estimated_jumps_saved(self) -> int | None:
        conventional = self.conventional_minimum_jumps
        if conventional is None:
            return None
        return conventional - self.actual_total_jumps

    @property
    def neutron_route_is_advantageous(self) -> bool | None:
        saved = self.estimated_jumps_saved
        return None if saved is None else saved > 0

    @classmethod
    def from_dict(cls, payload: dict) -> "SpanshRoutePlan":
        return cls(
            job_id=payload["job_id"],
            source_system=payload["source_system"],
            destination_system=payload["destination_system"],
            jump_range=float(payload["jump_range"]),
            efficiency=int(payload["efficiency"]),
            total_jumps=int(payload["total_jumps"]),
            distance=float(payload["distance"]),
            waypoints=tuple(
                SpanshWaypoint(
                    system=item["system"],
                    address=item.get("address"),
                    position=tuple(item["position"]),
                    distance_jumped=float(item["distance_jumped"]),
                    distance_left=float(item["distance_left"]),
                    jumps=int(item["jumps"]),
                    neutron_star=bool(item["neutron_star"]),
                )
                for item in payload["waypoints"]
            ),
            provider=payload.get("provider", "Spansh"),
            strategy=payload.get("strategy", "neutron_fastest"),
        )


@dataclass(frozen=True, slots=True)
class RouteClipboardUpdate:
    arrived_system: str
    copied_system: str | None
    route_complete: bool
    waypoint_index: int
    route_abandoned: bool = False
    jumps_completed: int = 0
    jumps_remaining: int = 0
    total_jumps: int = 0
    destination_system: str = ""


class SpanshClient:
    """Cliente acotado al planificador asíncrono de neutrones."""

    BASE_URL = "https://spansh.co.uk/api"

    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "ODIN-EliteCopilot/0.7 "
                "(Elite Dangerous navigation companion)"
            ),
            "Accept": "application/json",
        })
        self.sleeper = sleeper

    def plan_neutron_route(
        self,
        source: str,
        destination: str,
        jump_range: float,
        *,
        efficiency: int = 60,
        timeout: float = 120.0,
    ) -> SpanshRoutePlan:
        source = source.strip()
        destination = destination.strip()
        if not source or not destination:
            raise ValueError("Origen y destino son obligatorios.")
        if jump_range <= 0:
            raise ValueError("El alcance de salto debe ser mayor que cero.")
        if not 1 <= efficiency <= 100:
            raise ValueError("La eficiencia debe estar entre 1 y 100.")

        payload = self._get_json(
            f"{self.BASE_URL}/route",
            params={
                "efficiency": efficiency,
                "range": jump_range,
                "from": source,
                "to": destination,
            },
        )
        deadline = time.monotonic() + timeout
        delay = 0.5
        while payload.get("result") is None:
            job = payload.get("job")
            if not job:
                raise SpanshRouteError(payload.get("error", "Respuesta sin trabajo."))
            if time.monotonic() >= deadline:
                raise SpanshRouteError("Spansh superó el tiempo máximo de cálculo.")
            self.sleeper(delay)
            payload = self._get_json(f"{self.BASE_URL}/results/{job}")
            delay = min(delay * 1.6, 5.0)

        return self._decode_plan(payload["result"])

    def plan_exact_route(
        self, parameters: dict, *, timeout: float = 180.0
    ) -> ExactRoutePlan:
        """Ejecuta Galaxy Plotter únicamente con parámetros ya validados."""

        source = str(parameters.get("source", "")).strip()
        destination = str(parameters.get("destination", "")).strip()
        if not source or not destination:
            raise ValueError("Origen y destino exactos son obligatorios.")
        required = (
            "tank_size", "optimal_mass", "base_mass", "internal_tank_size",
            "max_fuel_per_jump", "fuel_power", "fuel_multiplier",
        )
        missing = tuple(name for name in required if not parameters.get(name))
        if missing:
            raise ValueError(
                "Faltan parámetros físicos exactos: " + ", ".join(missing)
            )
        payload = self._post_json(
            f"{self.BASE_URL}/generic/route", data=dict(parameters)
        )
        job_id = str(payload.get("job", ""))
        deadline = time.monotonic() + timeout
        delay = 0.5
        while payload.get("result") is None:
            if not job_id:
                raise SpanshRouteError(payload.get("error", "Respuesta sin trabajo."))
            if time.monotonic() >= deadline:
                raise SpanshRouteError("Galaxy Plotter superó el tiempo máximo de cálculo.")
            self.sleeper(delay)
            payload = self._get_json(f"{self.BASE_URL}/results/{job_id}")
            delay = min(delay * 1.6, 5.0)
        return self._decode_exact_plan(
            payload["result"], job_id=job_id,
            source=source, destination=destination,
        )

    def _get_json(self, url: str, *, params: dict | None = None) -> dict:
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise SpanshRouteError(f"Error consultando Spansh: {error}") from error
        if not isinstance(payload, dict):
            raise SpanshRouteError("Spansh devolvió una respuesta inesperada.")
        if payload.get("error"):
            raise SpanshRouteError(str(payload["error"]))
        return payload

    def _post_json(self, url: str, *, data: dict) -> dict:
        try:
            response = self.session.post(url, data=data, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise SpanshRouteError(f"Error consultando Spansh: {error}") from error
        if not isinstance(payload, dict):
            raise SpanshRouteError("Spansh devolvió una respuesta inesperada.")
        if payload.get("error"):
            raise SpanshRouteError(str(payload["error"]))
        return payload

    @staticmethod
    def _decode_exact_plan(
        result: dict, *, job_id: str, source: str, destination: str
    ) -> ExactRoutePlan:
        try:
            waypoints = tuple(
                ExactWaypoint(
                    system=str(item["name"]), address=item.get("id64"),
                    position=(float(item["x"]), float(item["y"]), float(item["z"])),
                    distance_jumped=float(item.get("distance", 0) or 0),
                    distance_left=float(item.get("distance_to_destination", 0) or 0),
                    fuel_in_tank=float(item.get("fuel_in_tank", 0) or 0),
                    fuel_used=float(item.get("fuel_used", 0) or 0),
                    scoopable=bool(item.get("is_scoopable")),
                    must_refuel=bool(item.get("must_refuel")),
                    neutron_star=bool(item.get("has_neutron")),
                )
                for item in result["jumps"]
            )
            if not waypoints:
                raise ValueError("ruta vacía")
            return ExactRoutePlan(job_id, source, destination, waypoints)
        except (KeyError, TypeError, ValueError) as error:
            raise SpanshRouteError(
                "Galaxy Plotter devolvió una ruta incompleta."
            ) from error

    @staticmethod
    def _decode_plan(result: dict) -> SpanshRoutePlan:
        try:
            waypoints = tuple(
                SpanshWaypoint(
                    system=item["system"],
                    address=item.get("id64"),
                    position=(float(item["x"]), float(item["y"]), float(item["z"])),
                    distance_jumped=float(item["distance_jumped"]),
                    distance_left=float(item["distance_left"]),
                    jumps=int(item["jumps"]),
                    neutron_star=bool(item["neutron_star"]),
                )
                for item in result["system_jumps"]
            )
            return SpanshRoutePlan(
                job_id=result["job"],
                source_system=result["source_system"],
                destination_system=result["destination_system"],
                jump_range=float(result["range"]),
                efficiency=int(result["efficiency"]),
                total_jumps=sum(waypoint.jumps for waypoint in waypoints[1:]),
                distance=float(result["distance"]),
                waypoints=waypoints,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SpanshRouteError("La ruta de Spansh está incompleta.") from error


class HeimdallRoutePlanner:
    """Planifica desde el contexto real y conserva una única ruta activa."""

    def __init__(
        self,
        database: DatabaseManager,
        client: SpanshClient,
        *,
        clipboard_writer: Callable[[str], None] = write_text,
    ) -> None:
        self.database = database
        self.client = client
        self.clipboard_writer = clipboard_writer

    def plan_fastest(
        self,
        context: NavigationContext,
        destination: str,
        *,
        efficiency: int = 60,
    ) -> SpanshRoutePlan:
        plan = self.calculate_fastest(context, destination, efficiency=efficiency)
        self.activate(plan)
        return plan

    def calculate_fastest(
        self,
        context: NavigationContext,
        destination: str,
        *,
        efficiency: int = 60,
    ) -> SpanshRoutePlan:
        """Calcula sin tocar SQLite ni portapapeles; apto para un hilo de red."""

        if not context.current_system:
            raise ValueError("HEIMDALL todavía no conoce el sistema actual.")
        if context.max_jump_range <= 0:
            raise ValueError("HEIMDALL todavía no conoce el alcance de la nave.")
        return self.client.plan_neutron_route(
            context.current_system,
            destination,
            context.max_jump_range,
            efficiency=efficiency,
        )

    def calculate_exact(
        self, context: NavigationContext, destination: str, *, cargo: int = 0,
        use_supercharge: bool = True, use_injections: bool = False,
    ) -> ExactRoutePlan:
        """Calcula fuera del hilo gráfico y sin activar una ruta incompleta."""

        parameters = context.exact_plotter_parameters(
            destination, cargo=cargo, use_supercharge=use_supercharge,
            use_injections=use_injections,
        )
        return self.client.plan_exact_route(parameters)
    @staticmethod
    def _plan_from_json(payload: str) -> SpanshRoutePlan | ExactRoutePlan:
        data = json.loads(payload)
        if data.get("strategy") == "galaxy_exact":
            return ExactRoutePlan.from_dict(data)
        return SpanshRoutePlan.from_dict(data)

    def activate(self, plan: SpanshRoutePlan | ExactRoutePlan) -> None:
        """Guarda el resultado y deja el primer waypoint en el portapapeles."""

        self.save_active(plan)
        if plan.next_waypoint is not None:
            self.clipboard_writer(plan.next_waypoint.system)

    def save_active(self, plan: SpanshRoutePlan | ExactRoutePlan) -> None:
        self.database.execute(
            "UPDATE heimdall_planned_routes SET status='replaced' WHERE status='active'"
        )
        self.database.execute(
            """
            INSERT INTO heimdall_planned_routes
            (source_system, destination_system, provider, strategy, jump_range,
             efficiency, total_jumps, distance, status, json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, datetime('now'))
            """,
            (
                plan.source_system,
                plan.destination_system,
                plan.provider,
                plan.strategy,
                float(getattr(plan, "jump_range", 0)),
                int(getattr(plan, "efficiency", 0)),
                plan.actual_total_jumps,
                plan.distance,
                json.dumps(asdict(plan), ensure_ascii=False),
            ),
        )

    def advance_if_arrived(
        self,
        system: str,
        current_route: tuple[str, ...] | list[str] | None = None,
    ) -> RouteClipboardUpdate | None:
        """Avanza al llegar o archiva el plan si el juego recalculó la ruta."""

        rows = self.database.query(
            """
            SELECT id, json, current_waypoint_index, jumps_completed,
                   last_arrived_system
            FROM heimdall_planned_routes
            WHERE status='active'
            ORDER BY id DESC LIMIT 1
            """
        )
        if not rows:
            return None
        row = rows[0]
        plan = self._plan_from_json(row["json"])
        index = int(row["current_waypoint_index"])
        completed = int(row["jumps_completed"])
        total = plan.actual_total_jumps
        if index >= len(plan.waypoints):
            return None
        expected = plan.waypoints[index]
        arrived = system.strip()
        if (
            arrived
            and arrived.casefold()
            == str(row["last_arrived_system"] or "").strip().casefold()
        ):
            return RouteClipboardUpdate(
                arrived_system=arrived,
                copied_system=None,
                route_complete=False,
                waypoint_index=index,
                jumps_completed=completed,
                jumps_remaining=max(0, total - completed),
                total_jumps=total,
                destination_system=plan.destination_system,
            )
        if expected.system.casefold() != system.strip().casefold():
            route_systems = {
                item.strip().casefold()
                for item in (current_route or ())
                if item and item.strip()
            }
            if route_systems and expected.system.casefold() not in route_systems:
                self.database.execute(
                    """
                    UPDATE heimdall_planned_routes
                    SET status='abandoned'
                    WHERE id=?
                    """,
                    (row["id"],),
                )
                return RouteClipboardUpdate(
                    arrived_system=system,
                    copied_system=None,
                    route_complete=False,
                    waypoint_index=index,
                    route_abandoned=True,
                    jumps_completed=completed,
                    jumps_remaining=max(0, total - completed),
                    total_jumps=total,
                    destination_system=plan.destination_system,
                )
            completed = min(total, completed + 1)
            self.database.execute(
                """
                UPDATE heimdall_planned_routes
                SET jumps_completed=?, last_arrived_system=? WHERE id=?
                """,
                (completed, arrived, row["id"]),
            )
            return RouteClipboardUpdate(
                arrived_system=system,
                copied_system=None,
                route_complete=False,
                waypoint_index=index,
                jumps_completed=completed,
                jumps_remaining=max(0, total - completed),
                total_jumps=total,
                destination_system=plan.destination_system,
            )

        completed = min(total, completed + 1)

        next_index = index + 1
        if next_index >= len(plan.waypoints):
            self.database.execute(
                """
                UPDATE heimdall_planned_routes
                SET status='completed', current_waypoint_index=?, jumps_completed=?,
                    last_arrived_system=?
                WHERE id=?
                """,
                (next_index, completed, arrived, row["id"]),
            )
            return RouteClipboardUpdate(
                system, None, True, next_index,
                jumps_completed=completed,
                jumps_remaining=0,
                total_jumps=total,
                destination_system=plan.destination_system,
            )

        next_system = plan.waypoints[next_index].system
        self.database.execute(
            """
            UPDATE heimdall_planned_routes
            SET current_waypoint_index=?, jumps_completed=?, last_arrived_system=?
            WHERE id=?
            """,
            (next_index, completed, arrived, row["id"]),
        )
        self.clipboard_writer(next_system)
        return RouteClipboardUpdate(
            system, next_system, False, next_index,
            jumps_completed=completed,
            jumps_remaining=max(0, total - completed),
            total_jumps=total,
            destination_system=plan.destination_system,
        )

    def copy_pending_waypoint(self) -> str | None:
        """Recupera una ruta activa sin adelantarla y copia su objetivo pendiente."""

        rows = self.database.query(
            """
            SELECT json, current_waypoint_index
            FROM heimdall_planned_routes
            WHERE status='active'
            ORDER BY id DESC LIMIT 1
            """
        )
        if not rows:
            return None
        plan = self._plan_from_json(rows[0]["json"])
        index = int(rows[0]["current_waypoint_index"])
        if index >= len(plan.waypoints):
            return None
        system = plan.waypoints[index].system
        self.clipboard_writer(system)
        return system

    def active_route_snapshot(self, context: NavigationContext | None = None) -> dict:
        """Resumen de sólo lectura para la interfaz, ejecutado por el hilo motor."""

        rows = self.database.query(
            """
            SELECT json, current_waypoint_index, jumps_completed
            FROM heimdall_planned_routes
            WHERE status='active'
            ORDER BY id DESC LIMIT 1
            """
        )
        if not rows:
            return {}
        plan = self._plan_from_json(rows[0]["json"])
        index = int(rows[0]["current_waypoint_index"])
        completed = int(rows[0]["jumps_completed"])
        total = plan.actual_total_jumps
        next_system = (
            plan.waypoints[index].system if 0 <= index < len(plan.waypoints) else ""
        )
        snapshot = {
            "destination": plan.destination_system,
            "next_system": next_system,
            "completed_jumps": completed,
            "remaining_jumps": max(0, total - completed),
            "total_jumps": total,
            "distance_ly": plan.distance,
            "strategy": plan.strategy,
        }
        if isinstance(plan, ExactRoutePlan) and 0 <= index < len(plan.waypoints):
            waypoint = plan.waypoints[index]
            snapshot["fuel_in_tank"] = waypoint.fuel_in_tank
            snapshot["fuel_used"] = waypoint.fuel_used
            snapshot["leg_distance_ly"] = waypoint.distance_jumped
            snapshot["must_refuel"] = waypoint.must_refuel
            snapshot["scoopable"] = waypoint.scoopable
            snapshot["neutron_star"] = waypoint.neutron_star
        conventional = (
            context.conventional_route_summary(plan.destination_system)
            if context is not None and isinstance(plan, SpanshRoutePlan) else {}
        )
        if conventional:
            conventional_total = int(conventional["total_jumps"])
            snapshot["conventional"] = conventional
            snapshot["exact_jumps_saved"] = conventional_total - total
            snapshot["comparison_source"] = conventional["source"]
        return snapshot
