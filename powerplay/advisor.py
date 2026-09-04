"""Actividades Powerplay y búsqueda comunitaria de zonas de combate."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import requests


class PowerplaySearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PowerplayActivity:
    key: str
    label: str
    verification: str
    objective: str


@dataclass(frozen=True, slots=True)
class CombatLocation:
    system: str
    distance_ly: float
    controlling_power: str
    power_state: str
    operation: str
    conflict: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


ACTIVITIES = {
    item.key: item for item in (
        PowerplayActivity("combat", "Combate", "contextual",
            "Buscar sistemas de refuerzo, adquisición o socavación con actividad de combate."),
        PowerplayActivity("trade", "Comercio", "experimental",
            "Comerciar sin carrier y confirmar los méritos exclusivamente con el Journal."),
        PowerplayActivity("mining", "Minería", "experimental",
            "Extraer minerales con la nave y venderlos en el territorio Powerplay elegido."),
        PowerplayActivity("transport", "Suministros", "direct",
            "Retirar y entregar suministros indicados por la interfaz Powerplay del juego."),
        PowerplayActivity("exploration", "Exploración", "unverified",
            "Usar cartografía o exobiología sólo si el panel actual las marca como válidas."),
        PowerplayActivity("on_foot", "Operaciones terrestres", "contextual",
            "Realizar adquisición, entrega de datos o sabotaje según territorio y ethos."),
        PowerplayActivity("salvage", "Rescate y salvamento", "contextual",
            "Recuperar y entregar únicamente objetivos identificados por Powerplay."),
    )
}


ACTIVITY_GUIDANCE = {
    "combat": "Comprobá los objetivos en Actividades locales.",
    "trade": "Comprobá beneficio, raros o inundación de mercado en Actividades locales.",
    "mining": "Confirmá en qué sistema extraer y en cuál vender el mineral.",
    "transport": "Retirá suministros en el contacto de la potencia y verificá el destino.",
    "exploration": "Entregá cartografía sólo donde Actividades locales la admita.",
    "on_foot": "Revisá el tipo exacto de operación requerido en el asentamiento.",
    "salvage": "Recuperá sólo cargamento identificado para Powerplay.",
}


class SpanshPowerplaySearchClient:
    URL = "https://spansh.co.uk/api/systems/search"

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def combat_locations(
        self, coordinates: tuple[float, float, float], pledged_power: str,
        *, max_distance_ly: float = 250.0, disputed_only: bool = True,
    ) -> tuple[CombatLocation, ...]:
        if len(coordinates) != 3 or not pledged_power.strip():
            raise ValueError("La posición y la potencia son obligatorias.")
        payload = {
            "filters": {
                "distance": {"min": 0, "max": max_distance_ly},
                "power": {"value": pledged_power.strip()},
            },
            # Las disputas cambian durante el ciclo. Consultar primero los
            # registros recientes evita que queden enterradas entre miles de
            # sistemas explotados cercanos.
            "sort": [{
                "updated_at" if disputed_only else "distance": {
                    "direction": "desc" if disputed_only else "asc"
                }
            }],
            "size": 100, "page": 0,
            "reference_coords": {
                "x": coordinates[0], "y": coordinates[1], "z": coordinates[2],
            },
        }
        rows = []
        # Spansh limita cada página aunque se solicite un tamaño mayor. Cinco
        # páginas recientes cubren el ciclo activo sin recorrer su catálogo
        # histórico completo. Para el resto de actividades basta la más cercana.
        pages = range(5) if disputed_only else range(1)
        try:
            for page in pages:
                payload["page"] = page
                response = self.session.post(
                    self.URL, json=payload, timeout=35,
                    headers={"User-Agent": "ODIN Elite Copilot"},
                )
                response.raise_for_status()
                result = response.json()
                page_rows = result.get("results")
                if not isinstance(page_rows, list):
                    raise PowerplaySearchError(
                        "Spansh devolvió una búsqueda Powerplay inválida."
                    )
                rows.extend(page_rows)
        except (requests.RequestException, ValueError, TypeError) as error:
            raise PowerplaySearchError(
                "No se pudieron consultar ubicaciones de combate Powerplay."
            ) from error
        parser = self._records if disputed_only else self._territory_records
        return parser(rows, pledged_power, max_distance_ly)

    def activity_locations(
        self, coordinates: tuple[float, float, float], pledged_power: str,
        activity: str, *, max_distance_ly: float = 250.0,
    ) -> tuple[CombatLocation, ...]:
        """Busca territorios candidatos tras una acción explícita del usuario."""

        if activity not in ACTIVITIES:
            raise ValueError("Actividad Powerplay desconocida.")
        return self.combat_locations(
            coordinates, pledged_power, max_distance_ly=max_distance_ly,
            disputed_only=activity == "combat",
        )

    @staticmethod
    def _territory_records(rows, pledged_power: str, maximum: float):
        """Conserva territorios de la potencia para actividades no bélicas."""

        wanted = pledged_power.casefold()
        locations = []
        for row in rows:
            system = str(row.get("name", row.get("system_name", "")) or "")
            distance = float(row.get("distance", 0) or 0)
            if not system or distance > maximum:
                continue
            controlling = str(row.get(
                "controlling_power", row.get("system_controlling_power", "")
            ) or "")
            powers = row.get("powers", row.get("power", ())) or ()
            if isinstance(powers, str):
                powers = (powers,)
            state = str(row.get("power_state", row.get("powerplay_state", "")) or "")
            if not (
                controlling.casefold() == wanted
                or any(str(power).casefold() == wanted for power in powers)
                or wanted in SpanshPowerplaySearchClient._power_conflict_progress(row)
            ):
                continue
            if controlling.casefold() == wanted:
                operation = "reinforce"
            elif controlling:
                operation = "undermine"
            else:
                operation = "acquire"
            locations.append(CombatLocation(
                system, distance, controlling, state, operation, "",
                str(row.get("updated_at", "") or ""),
            ))
        return tuple(sorted(locations, key=lambda item: item.distance_ly))

    @staticmethod
    def _records(rows, pledged_power: str, maximum: float):
        """Devuelve sólo disputas Powerplay reales de la potencia indicada.

        Spansh no siempre publica ``power_state=Contested`` (HR 858, por
        ejemplo, puede llegar como ``Unoccupied``).  La señal estable es
        ``power_conflict_progress``: la potencia jurada y al menos un rival
        deben tener progreso registrado. Las guerras BGS de ``conflicts`` no
        son actividad Powerplay y se ignoran deliberadamente.
        """

        wanted = pledged_power.casefold()
        locations = []
        for row in rows:
            system = str(row.get("name", row.get("system_name", "")) or "")
            distance = float(row.get("distance", 0) or 0)
            if not system or distance > maximum:
                continue
            controlling = str(row.get(
                "controlling_power", row.get("system_controlling_power", "")
            ) or "")
            state = str(row.get("power_state", row.get("powerplay_state", "")) or "")
            progress = SpanshPowerplaySearchClient._power_conflict_progress(row)
            pledged_progress = progress.get(wanted)
            opponents = [
                value for power, value in progress.items() if power != wanted
            ]
            powers = row.get("powers", row.get("power", ())) or ()
            if isinstance(powers, str):
                powers = (powers,)
            participates = wanted in progress or any(
                str(power).strip().casefold() == wanted for power in powers
            )
            explicitly_contested = (
                state.casefold() in {"contested", "disputed"} and participates
            )
            inferred_contested = bool(
                pledged_progress is not None
                # En expansiones ordinarias puede aparecer una potencia rival
                # con progreso alto y una participación testimonial de la
                # potencia jurada. Una disputa efectiva requiere que ambos
                # bandos hayan superado el umbral de conflicto comunitario.
                and pledged_progress >= 0.5
                and opponents
                and max(opponents) >= 0.5
            )
            if not (explicitly_contested or inferred_contested):
                continue
            operation = "undermine"
            conflict = "Disputa Powerplay"
            locations.append(CombatLocation(
                system, distance, controlling, state or "Disputed", operation, conflict,
                str(row.get("updated_at", "") or ""),
            ))
        return tuple(sorted(locations, key=lambda item: item.distance_ly))

    @staticmethod
    def _power_conflict_progress(row) -> dict[str, float]:
        raw = row.get("power_conflict_progress", ()) or ()
        if isinstance(raw, dict):
            raw = raw.items()
        else:
            raw = (
                (
                    item.get("power", item.get("name", "")),
                    item.get("progress", item.get("value", 0)),
                )
                for item in raw if isinstance(item, dict)
            )
        progress = {}
        for power, value in raw:
            try:
                progress[str(power).casefold()] = float(value or 0)
            except (TypeError, ValueError):
                continue
        return progress


def activity_snapshot(state, selected: dict | None = None) -> dict:
    selected = selected or {}
    activity = ACTIVITIES.get(str(selected.get("key", "")))
    merits = int(getattr(state, "powerplay_merits", 0) or 0)
    start = int(selected.get("start_merits", merits) or 0)
    return {
        "pledged": bool(getattr(state, "powerplay_power", "")),
        "power": str(getattr(state, "powerplay_power", "") or ""),
        "rank": int(getattr(state, "powerplay_rank", 0) or 0),
        "merits": merits, "earned": max(0, merits - start) if activity else 0,
        "selected": activity.key if activity else "",
        "activity": activity.label if activity else "Sin actividad elegida",
        "verification": activity.verification if activity else "",
        "objective": activity.objective if activity else "Elegí cómo querés conseguir méritos.",
        "guidance": ACTIVITY_GUIDANCE.get(activity.key, "") if activity else "",
        "system": str(getattr(state, "current_system", "") or ""),
        "controlling_power": str(getattr(state, "controlling_power", "") or ""),
        "system_state": str(getattr(state, "powerplay_state", "") or ""),
        "reinforcement": int(getattr(state, "powerplay_reinforcement", 0) or 0),
        "undermining": int(getattr(state, "powerplay_undermining", 0) or 0),
        "calculating": bool(selected.get("calculating")),
        "locations": list(selected.get("locations", ())),
        "subject": str(selected.get("subject", "")),
        "source_warning": str(selected.get("source_warning", "")),
        "sources": list(selected.get("sources", ())),
        "error": str(selected.get("error", "")),
    }


def match_mining_locations(territories, mining_locations) -> list[dict]:
    """Cruza hotspots con los sistemas territoriales candidatos."""

    by_system = {item.system.casefold(): item for item in territories}
    matches = []
    for hotspot in mining_locations:
        territory = by_system.get(hotspot.system.casefold())
        if territory is None:
            continue
        record = territory.to_dict()
        record.update({
            "body": hotspot.body, "ring": hotspot.ring,
            "ring_type": hotspot.ring_type,
            "reserve_level": hotspot.reserve_level,
            "hotspot_count": hotspot.hotspot_count,
            "distance_ls": hotspot.distance_ls,
        })
        matches.append(record)
    return matches


def build_powerplay_mining_plan(territories, mining_locations, sales) -> list[dict]:
    """Construye los dos tramos de la operación: extracción y entrega.

    Un hotspot no necesita estar dentro del territorio Powerplay. La carga debe
    conservar su procedencia desde la refinería y venderse después en una
    estación elegible del territorio indicado por Actividades locales.
    """

    plan = []
    seen_hotspots = set()
    for hotspot in mining_locations:
        key = (hotspot.system.casefold(), hotspot.ring.casefold())
        if key in seen_hotspots:
            continue
        seen_hotspots.add(key)
        record = hotspot.to_dict()
        record.update({
            "operation": "mine",
            "power_state": "Extracción",
            "instructions": "Extraé y refiná el mineral; no lo transfieras a un carrier.",
        })
        plan.append(record)
        if len(seen_hotspots) >= 3:
            break

    territory_by_system = {item.system.casefold(): item for item in territories}
    for sale in sales:
        territory = territory_by_system.get(str(sale.get("system_name", "")).casefold())
        if territory is None:
            continue
        record = territory.to_dict()
        record.update({
            "station": str(sale.get("station_name", "")),
            "sell_price": int(sale.get("sell_price", 0) or 0),
            "demand": int(sale.get("demand", 0) or 0),
            "has_large_pad": bool(sale.get("has_large_pad", False)),
            "market_updated_at": str(sale.get("updated_at", "") or ""),
            "power_state": territory.power_state or "Entrega Powerplay",
            "instructions": (
                "Vendé aquí sólo si Actividades locales confirma minería como "
                "actividad válida; los méritos se confirman por el Journal."
            ),
        })
        plan.append(record)
        if len(plan) >= 6:
            break
    return plan


def match_station_locations(territories, stations, purpose: str) -> list[dict]:
    """Cruza territorios con servicios conservados en la caché de estaciones."""

    by_system = {item.system.casefold(): item for item in territories}
    matches = []
    for station in stations:
        territory = by_system.get(str(station.get("system_name", "")).casefold())
        if territory is None:
            continue
        try:
            raw_services = json.loads(station.get("services_json") or "[]")
        except (TypeError, ValueError):
            raw_services = []
        services = {
            " ".join(str(item).casefold().replace("_", " ").split())
            for item in raw_services
        }
        station_type = str(station.get("station_type", "")).casefold()
        eligible = {
            "exploration": "universal cartographics" in services,
            "salvage": bool({"search and rescue", "search rescue"} & services),
            "on_foot": "settlement" in station_type or "asentamiento" in station_type,
        }.get(str(purpose), False)
        if not eligible:
            continue
        record = territory.to_dict()
        record.update({
            "station": str(station.get("station_name", "")),
            "has_large_pad": bool(station.get("has_large_pad")),
            "is_planetary": bool(station.get("is_planetary")),
            "distance_ls": float(station.get("distance_to_arrival", 0) or 0),
            "station_type": str(station.get("station_type", "")),
            "services": sorted(services),
            "contact_unverified": True,
        })
        matches.append(record)
    return matches
