"""Auditoría conservadora del equipamiento minero informado por Loadout."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class TechniqueAssessment:
    ready: bool
    missing: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"ready": self.ready, "missing": list(self.missing)}


@dataclass(frozen=True, slots=True)
class MiningEquipmentAudit:
    ship: str
    cargo_capacity: int
    modules: dict[str, bool]
    techniques: dict[str, TechniqueAssessment]

    def to_dict(self) -> dict:
        return {
            "ship": self.ship,
            "cargo_capacity": self.cargo_capacity,
            "modules": dict(self.modules),
            "techniques": {
                name: assessment.to_dict()
                for name, assessment in self.techniques.items()
            },
        }


MODULE_PATTERNS = {
    "mining_laser": ("hpt_miningtool",),
    "abrasion_blaster": ("hpt_mining_abrblstr",),
    "subsurface_missile": ("hpt_mining_subsurfdispmisle",),
    "seismic_launcher": ("hpt_mining_seismchrgwarhd",),
    "pulse_wave": ("hpt_mrascanner",),
    "refinery": ("int_refinery",),
    "prospector": ("dronecontrol_prospector", "multidronecontrol_mining"),
    "collector": ("dronecontrol_collection", "multidronecontrol_mining"),
    "cargo_rack": ("int_cargorack",),
}

DISPLAY_NAMES = {
    "mining_laser": "láser minero",
    "abrasion_blaster": "bláster de abrasión",
    "subsurface_missile": "misiles subsuperficiales",
    "seismic_launcher": "lanzador de cargas sísmicas",
    "pulse_wave": "analizador de ondas de pulso",
    "refinery": "refinería",
    "prospector": "controlador prospector",
    "collector": "controlador recolector",
    "cargo_rack": "bodega de carga",
}

TECHNIQUE_REQUIREMENTS = {
    "laser": (
        "mining_laser", "refinery", "prospector", "collector", "cargo_rack",
    ),
    "abrasion": (
        "abrasion_blaster", "refinery", "prospector", "collector", "cargo_rack",
    ),
    "subsurface": (
        "subsurface_missile", "pulse_wave", "refinery", "prospector",
        "collector", "cargo_rack",
    ),
    "core": (
        "seismic_launcher", "abrasion_blaster", "pulse_wave", "refinery",
        "prospector", "collector", "cargo_rack",
    ),
}

SHIP_NAMES = {
    # Nombre interno usado por el Journal para la nueva nave minera de Lakon.
    "lakonminer": "Type-11 Prospector",
}


def audit_mining_loadout(event: dict) -> MiningEquipmentAudit:
    installed = [
        str(module.get("Item", "") or "").casefold()
        for module in event.get("Modules", ()) or ()
        if module.get("On", True)
    ]
    modules = {
        capability: any(
            pattern in item for item in installed for pattern in patterns
        )
        for capability, patterns in MODULE_PATTERNS.items()
    }
    cargo_capacity = max(0, int(event.get("CargoCapacity", 0) or 0))
    modules["cargo_rack"] = modules["cargo_rack"] and cargo_capacity > 0
    techniques = {}
    for technique, requirements in TECHNIQUE_REQUIREMENTS.items():
        missing = tuple(
            DISPLAY_NAMES[requirement]
            for requirement in requirements
            if not modules.get(requirement, False)
        )
        techniques[technique] = TechniqueAssessment(not missing, missing)
    internal_ship = str(event.get("Ship") or "").strip()
    ship_type = str(
        event.get("Ship_Localised")
        or SHIP_NAMES.get(internal_ship.casefold())
        or internal_ship
        or "Nave desconocida"
    ).strip()
    custom_name = str(event.get("ShipName") or "").strip()
    ship = f"{custom_name} · {ship_type}" if custom_name else ship_type
    return MiningEquipmentAudit(ship, cargo_capacity, modules, techniques)
