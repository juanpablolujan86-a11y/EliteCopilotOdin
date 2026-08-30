"""Recetas e inventario para desbloqueos de módulos Guardian."""

from __future__ import annotations

import re


GUARDIAN_MODULE_RECIPES = {
    "fsd_booster": {
        "label": "Potenciador del MDD Guardián",
        "requirements": {
            "guardian_moduleblueprint": ("Plano de módulo Guardián", 1),
            "guardian_powercell": ("Célula de energía Guardián", 21),
            "guardian_techcomponent": ("Componente tecnológico Guardián", 21),
            "focuscrystals": ("Cristales de enfoque", 24),
            "hnshockmount": ("Soportes amortiguadores HN", 8),
        },
    },
    "hull_reinforcement": {
        "label": "Refuerzo de casco Guardián",
        "requirements": {
            "guardian_moduleblueprint": ("Plano de módulo Guardián", 1),
            "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 21),
            "ancientculturaldata": ("Datos de obelisco patrón beta", 16),
            "ancienthistoricaldata": ("Datos de obelisco patrón gamma", 16),
            "reinforcedmountingplate": ("Placas de montaje reforzadas", 12),
        },
    },
    "hybrid_power_distributor": {
        "label": "Distribuidor de energía híbrido Guardián",
        "requirements": {
            "guardian_moduleblueprint": ("Plano de módulo Guardián", 1),
            "ancientbiologicaldata": ("Datos de obelisco patrón alfa", 20),
            "guardian_powercell": ("Célula de energía Guardián", 24),
            "phasealloys": ("Aleaciones de fase", 18),
            "heatsinkinterlink": ("Interconectores de disipador", 6),
        },
    },
    "module_reinforcement": {
        "label": "Refuerzo de módulos Guardián",
        "requirements": {
            "guardian_moduleblueprint": ("Plano de módulo Guardián", 1),
            "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 18),
            "ancienttechnologicaldata": ("Datos de obelisco patrón epsilon", 15),
            "guardian_powerconduit": ("Conducto de energía Guardián", 20),
            "reinforcedmountingplate": ("Placas de montaje reforzadas", 9),
        },
    },
    "power_plant": {
        "label": "Planta de energía Guardián",
        "requirements": {
            "guardian_moduleblueprint": ("Plano de módulo Guardián", 1),
            "guardian_powerconduit": ("Conducto de energía Guardián", 18),
            "ancienttechnologicaldata": ("Datos de obelisco patrón epsilon", 21),
            "heatresistantceramics": ("Cerámicas resistentes al calor", 15),
            "energygridassembly": ("Conjuntos de red energética", 10),
        },
    },
    "shield_reinforcement": {
        "label": "Refuerzo de escudo Guardián",
        "requirements": {
            "guardian_moduleblueprint": ("Plano de módulo Guardián", 1),
            "guardian_powercell": ("Célula de energía Guardián", 17),
            "guardian_techcomponent": ("Componente tecnológico Guardián", 20),
            "ancientlanguagedata": ("Datos de obelisco patrón delta", 24),
            "hardwarediagnosticsensor": ("Sensores de diagnóstico de hardware", 8),
        },
    },
}


def _recipe(label: str, requirements: dict, category: str) -> dict:
    return {"label": label, "requirements": requirements, "category": category}


# Desbloqueos Guardian permanentes adicionales. Las armas modificadas de Mbooni
# son compras por unidad y se mantendrán en un catálogo separado.
GUARDIAN_MODULE_RECIPES.update({
    "gauss_fixed_1": _recipe("Arma · Cañón Gauss fijo C1", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powerconduit": ("Conducto de energía Guardián", 12),
        "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 12),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 15),
    }, "weapon"),
    "gauss_fixed_2": _recipe("Arma · Cañón Gauss fijo C2", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powercell": ("Célula de energía Guardián", 18),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 20),
        "manganese": ("Manganeso", 15),
        "magneticemittercoil": ("Bobinas de emisor magnético", 6),
    }, "weapon"),
    "plasma_fixed_1": _recipe("Arma · Cargador de plasma fijo C1", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powercell": ("Célula de energía Guardián", 12),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 12),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 15),
    }, "weapon"),
    "plasma_fixed_2": _recipe("Arma · Cargador de plasma fijo C2", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powerconduit": ("Conducto de energía Guardián", 19),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 16),
        "chromium": ("Cromo", 14),
        "microweavecoolinghoses": ("Mangueras de refrigeración microtejidas", 8),
    }, "weapon"),
    "plasma_fixed_3": _recipe("Arma · Cargador de plasma fijo C3", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powerconduit": ("Conducto de energía Guardián", 28),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 20),
        "chromium": ("Cromo", 28),
        "microweavecoolinghoses": ("Mangueras de refrigeración microtejidas", 10),
    }, "weapon"),
    "plasma_turret_1": _recipe("Arma · Cargador de plasma torreta C1", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powercell": ("Célula de energía Guardián", 12),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 12),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 15),
    }, "weapon"),
    "plasma_turret_2": _recipe("Arma · Cargador de plasma torreta C2", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 2),
        "guardian_powerconduit": ("Conducto de energía Guardián", 21),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 20),
        "chromium": ("Cromo", 16),
        "articulationmotors": ("Motores de articulación", 8),
    }, "weapon"),
    "plasma_turret_3": _recipe("Arma · Cargador de plasma torreta C3", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 2),
        "guardian_powerconduit": ("Conducto de energía Guardián", 26),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 24),
        "chromium": ("Cromo", 26),
        "articulationmotors": ("Motores de articulación", 10),
    }, "weapon"),
    "shard_fixed_1": _recipe("Arma · Cañón de fragmentación fijo C1", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powerconduit": ("Conducto de energía Guardián", 12),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 12),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 15),
    }, "weapon"),
    "shard_fixed_2": _recipe("Arma · Cañón de fragmentación fijo C2", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 20),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 18),
        "carbon": ("Carbono", 14),
        "powertransferbus": ("Bus de transferencia de energía", 12),
    }, "weapon"),
    "shard_fixed_3": _recipe("Arma · Cañón de fragmentación fijo C3", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 20),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 28),
        "carbon": ("Carbono", 20),
        "microcontrollers": ("Microcontroladores", 18),
    }, "weapon"),
    "shard_turret_1": _recipe("Arma · Cañón de fragmentación torreta C1", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 1),
        "guardian_powerconduit": ("Conducto de energía Guardián", 12),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 15),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 12),
    }, "weapon"),
    "shard_turret_2": _recipe("Arma · Cañón de fragmentación torreta C2", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 2),
        "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 16),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 20),
        "carbon": ("Carbono", 15),
        "microcontrollers": ("Microcontroladores", 12),
    }, "weapon"),
    "shard_turret_3": _recipe("Arma · Cañón de fragmentación torreta C3", {
        "guardian_weaponblueprint": ("Plano de arma Guardián", 2),
        "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 20),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 28),
        "carbon": ("Carbono", 28),
        "microcontrollers": ("Microcontroladores", 12),
    }, "weapon"),
    "fighter_trident": _recipe("Caza · XG7 Trident", {
        "guardian_vesselblueprint": ("Plano de nave Guardián", 1),
        "guardian_powercell": ("Célula de energía Guardián", 25),
        "ancienttechnologicaldata": ("Datos de obelisco patrón epsilon", 26),
        "ancientculturaldata": ("Datos de obelisco patrón beta", 18),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 25),
    }, "fighter"),
    "fighter_javelin": _recipe("Caza · XG8 Javelin", {
        "guardian_vesselblueprint": ("Plano de nave Guardián", 1),
        "guardian_powercell": ("Célula de energía Guardián", 25),
        "ancienttechnologicaldata": ("Datos de obelisco patrón epsilon", 26),
        "guardian_sentinel_wreckagecomponents": ("Restos de Guardián", 18),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 25),
    }, "fighter"),
    "fighter_lance": _recipe("Caza · XG9 Lance", {
        "guardian_vesselblueprint": ("Plano de nave Guardián", 1),
        "guardian_powercell": ("Célula de energía Guardián", 25),
        "ancienttechnologicaldata": ("Datos de obelisco patrón epsilon", 26),
        "guardian_sentinel_weaponparts": ("Piezas de arma de centinela", 18),
        "guardian_techcomponent": ("Componente tecnológico Guardián", 25),
    }, "fighter"),
})

for _module in GUARDIAN_MODULE_RECIPES.values():
    _module.setdefault("category", "module")


class GuardianUnlockTracker:
    EVENTS = (
        "Materials", "MaterialCollected", "MaterialDiscarded", "MaterialTrade",
        "MissionCompleted", "Cargo", "CollectCargo", "EjectCargo", "MarketBuy",
        "MarketSell", "CargoTransfer",
    )

    def __init__(self) -> None:
        self.materials: dict[str, int] = {}
        self.cargo: dict[str, int] = {}

    @staticmethod
    def _name(value) -> str:
        return re.sub(r"[^a-z0-9_]", "", str(value or "").casefold().strip("$;"))

    def handle(self, event: dict) -> None:
        kind = str(event.get("event", ""))
        if kind == "Materials":
            self.materials = {
                self._name(item.get("Name")): max(0, int(item.get("Count", 0) or 0))
                for category in ("Raw", "Manufactured", "Encoded")
                for item in (event.get(category, ()) or ())
                if self._name(item.get("Name"))
            }
        elif kind in {"MaterialCollected", "MaterialDiscarded"}:
            name = self._name(event.get("Name"))
            amount = max(0, int(event.get("Count", 0) or 0))
            sign = 1 if kind == "MaterialCollected" else -1
            self.materials[name] = max(0, self.materials.get(name, 0) + sign * amount)
        elif kind == "MaterialTrade":
            for field, sign in (("Paid", -1), ("Received", 1)):
                item = event.get(field, {}) or {}
                name = self._name(item.get("Material"))
                amount = max(0, int(item.get("Quantity", 0) or 0))
                if name:
                    self.materials[name] = max(0, self.materials.get(name, 0) + sign * amount)
        elif kind == "MissionCompleted":
            for item in event.get("MaterialsReward", ()) or ():
                self._adjust(self.materials, item.get("Name"), item.get("Count", 0))
        elif kind == "Cargo" and "Inventory" in event:
            self.cargo = {
                self._name(item.get("Name")): max(0, int(item.get("Count", 0) or 0))
                for item in event.get("Inventory", ()) or ()
                if self._name(item.get("Name"))
            }
        elif kind in {"CollectCargo", "MarketBuy"}:
            self._adjust(self.cargo, event.get("Type"), event.get("Count", 1))
        elif kind in {"EjectCargo", "MarketSell"}:
            self._adjust(self.cargo, event.get("Type"), -int(event.get("Count", 1) or 1))
        elif kind == "CargoTransfer":
            for item in event.get("Transfers", ()) or ():
                direction = self._name(item.get("Direction"))
                sign = -1 if direction == "tocarrier" else 1
                self._adjust(self.cargo, item.get("Type"), sign * int(item.get("Count", 0) or 0))

    def _adjust(self, inventory: dict[str, int], name, delta) -> None:
        key = self._name(name)
        if key:
            inventory[key] = max(0, inventory.get(key, 0) + int(delta or 0))

    def snapshot(self) -> dict:
        inventory = dict(self.materials)
        inventory.update(self.cargo)
        modules = {}
        for key, recipe in GUARDIAN_MODULE_RECIPES.items():
            requirements = []
            complete = True
            for material, (label, required) in recipe["requirements"].items():
                available = max(0, int(inventory.get(material, 0)))
                missing = max(0, required - available)
                complete = complete and missing == 0
                requirements.append({
                    "material": material, "label": label, "required": required,
                    "available": available, "missing": missing,
                })
            modules[key] = {
                "label": recipe["label"], "complete": complete,
                "category": recipe.get("category", "module"),
                "requirements": requirements,
            }
        return {"modules": modules}
