"""Planificador comunitario de recolección y desbloqueo Guardian."""

from __future__ import annotations

import math
import json
from dataclasses import dataclass
from pathlib import Path

import requests


MODULE_SITES = (
    ("Synuefe NL-N c23-4", "B 3", (860.125, -124.59375, -61.0625)),
    ("Synuefe GT-H b43-1", "C 4", (749.0, -163.09375, -128.0625)),
    ("Col 173 Sector GS-J b25-4", "D 2", (957.03125, -142.0, -160.53125)),
    ("HD 63154", "B 3 a", (979.46875, -207.40625, -131.59375)),
    ("Vela Dark Region DL-Y d112", "1 a", (924.46875, -171.8125, -98.21875)),
)
WEAPON_SITES = (
    ("Synuefe EU-Q c21-10", "A 3", (758.65625, -176.90625, -133.21875)),
    ("Synuefe ZL-J d10-119", "9 B", (834.21875, -51.21875, -154.65625)),
)
VESSEL_SITES = (
    ("Synuefe EU-Q c21-15", "A 1", (754.15625, -171.84375, -138.09375)),
    ("Synuefe EN-H d11-96", "7 A", (757.125, -179.3125, -96.0625)),
)

MANUFACTURED = frozenset({"focuscrystals", "phasealloys", "heatresistantceramics"})
RAW = frozenset({"carbon", "chromium", "manganese"})
GUARDIAN_SITE_MATERIALS = frozenset({
    "guardian_moduleblueprint", "guardian_powercell", "guardian_techcomponent",
    "guardian_weaponblueprint", "guardian_vesselblueprint",
    "guardian_sentinel_wreckagecomponents", "guardian_powerconduit",
    "guardian_sentinel_weaponparts",
    "ancientbiologicaldata", "ancientculturaldata", "ancienthistoricaldata",
    "ancientlanguagedata", "ancienttechnologicaldata",
})
COMMODITY_NAMES = {
    "hnshockmount": "HN Shock Mount",
    "reinforcedmountingplate": "Reinforced Mounting Plate",
    "heatsinkinterlink": "Heatsink Interlink",
    "energygridassembly": "Energy Grid Assembly",
    "hardwarediagnosticsensor": "Hardware Diagnostic Sensor",
    "magneticemittercoil": "Magnetic Emitter Coil",
    "microweavecoolinghoses": "Micro-Weave Cooling Hoses",
    "articulationmotors": "Articulation Motors",
    "powertransferbus": "Power Transfer Bus",
    "microcontrollers": "Micro Controllers",
}


class GuardianSearchError(RuntimeError):
    pass


class GuardianPlanStore:
    """Persistencia atómica del último plan comunitario confirmado."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(value, dict) or not value.get("module_key"):
            return {}
        value["restored"] = True
        value["calculating"] = False
        return value

    def save(self, plan: dict) -> None:
        if not plan.get("module_key") or plan.get("error"):
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(plan)
        payload.pop("calculating", None)
        payload.pop("restored", None)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)


@dataclass(frozen=True)
class GuardianDestination:
    system: str
    location: str
    distance_ly: float
    purpose: str
    provider: str = "Spansh"

    def to_dict(self) -> dict:
        return {
            "system": self.system, "location": self.location,
            "distance_ly": self.distance_ly, "purpose": self.purpose,
            "provider": self.provider,
        }


class GuardianSearchClient:
    BASE_URL = "https://spansh.co.uk/api/stations/search"

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "ODIN-EliteCopilot/0.7 (Guardian unlock planner)",
            "Accept": "application/json",
        })

    def plan(self, module: dict, origin: tuple[float, float, float]) -> dict:
        missing = {
            item["material"]: item
            for item in module.get("requirements", ())
            if int(item.get("missing", 0) or 0) > 0
        }
        collection = []
        if GUARDIAN_SITE_MATERIALS.intersection(missing):
            category = str(module.get("category", "module"))
            sites = {
                "weapon": WEAPON_SITES,
                "fighter": VESSEL_SITES,
            }.get(category, MODULE_SITES)
            blueprint_label = {
                "weapon": "arma",
                "fighter": "nave",
            }.get(category, "módulo")
            system, body, coordinates = min(
                sites, key=lambda item: math.dist(origin, item[2])
            )
            collection.append(GuardianDestination(
                system, f"Estructura Guardiana · {body}",
                math.dist(origin, coordinates),
                f"Plano de {blueprint_label}, componentes Guardian y datos",
                "Canonn/EDSM",
            ).to_dict())
        if MANUFACTURED.intersection(missing):
            trader = self._nearest_station(
                origin, "Material Trader", self._is_manufactured_trader
            )
            if trader:
                trader["purpose"] = "Intercambio de materiales manufacturados"
                collection.append(trader)
        if RAW.intersection(missing):
            trader = self._nearest_station(
                origin, "Material Trader", self._is_raw_trader
            )
            if trader:
                trader["purpose"] = "Intercambio de materias primas"
                collection.append(trader)
        for material in COMMODITY_NAMES.keys() & missing.keys():
            market = self._nearest_market(origin, COMMODITY_NAMES[material])
            if market:
                market["purpose"] = f"Comprar {COMMODITY_NAMES[material]}"
                collection.append(market)
        broker = self._nearest_station(
            origin, "Technology Broker", self._is_guardian_broker
        )
        if broker:
            broker["purpose"] = "Desbloquear el módulo en agente tecnológico Guardian"
        return {
            "collection": collection, "broker": broker or {},
            "provider": "Spansh", "error": "",
        }

    def _search(self, origin, service: str | None, page: int, size: int = 25):
        filters = {"has_market": {"value": True}}
        if service:
            filters = {"services": {"name": {"value": service}}}
        payload = {
            "filters": filters,
            "sort": [{"distance": {"direction": "asc"}}],
            "size": size, "page": page,
            "reference_coords": {"x": origin[0], "y": origin[1], "z": origin[2]},
        }
        try:
            response = self.session.post(self.BASE_URL, json=payload, timeout=25)
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError, TypeError) as error:
            raise GuardianSearchError(f"No se pudo consultar Spansh: {error}") from error
        rows = result.get("results")
        if not isinstance(rows, list):
            raise GuardianSearchError("Spansh devolvió una búsqueda inválida.")
        return rows

    def _nearest_station(self, origin, service, predicate):
        for page in range(4):
            for station in self._search(origin, service, page):
                if predicate(station):
                    return self._station_data(station)
        return None

    def _nearest_market(self, origin, commodity: str):
        wanted = commodity.casefold()
        for page in range(6):
            for station in self._search(origin, None, page):
                available = next((
                    item for item in station.get("market", ()) or ()
                    if str(item.get("commodity", "")).casefold() == wanted
                    and int(item.get("supply", 0) or 0) > 0
                ), None)
                if available:
                    result = self._station_data(station)
                    result["stock"] = int(available.get("supply", 0) or 0)
                    return result
        return None

    @staticmethod
    def _is_manufactured_trader(station: dict) -> bool:
        explicit = str(station.get("material_trader", "")).casefold()
        if explicit:
            return explicit == "manufactured"
        economies = {
            str(station.get("primary_economy", "")).casefold(),
            str(station.get("system_primary_economy", "")).casefold(),
        }
        return "industrial" in economies

    @staticmethod
    def _is_raw_trader(station: dict) -> bool:
        explicit = str(station.get("material_trader", "")).casefold()
        if explicit:
            return explicit == "raw"
        economies = {
            str(station.get("primary_economy", "")).casefold(),
            str(station.get("system_primary_economy", "")).casefold(),
        }
        return "extraction" in economies or "refinery" in economies

    @staticmethod
    def _is_guardian_broker(station: dict) -> bool:
        verified_modules = (
            "guardian frame shift drive booster", "guardian gauss cannon",
            "guardian shard cannon", "guardian plasma charger",
            "guardian shield reinforcement", "guardian module reinforcement",
            "guardian hull reinforcement", "guardian hybrid power",
        )
        return any(
            any(token in str(module.get("name", "")).casefold()
                for token in verified_modules)
            for module in station.get("modules", ()) or ()
        )

    @staticmethod
    def _station_data(station: dict) -> dict:
        return GuardianDestination(
            str(station.get("system_name", "")), str(station.get("name", "")),
            float(station.get("distance", 0) or 0), "",
        ).to_dict()
