"""Estado verificable de ingenieros y planes de materiales de ingeniería."""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


ENGINEERS = {
    "Felicity Farseer": {"system": "Deciat", "station": "Farseer Inc", "unlock": "Alcanzar Explorador y entregar 1 Metaaleación.", "specialties": "MDD, motores, sensores y exploración"},
    "Elvira Martuuk": {"system": "Khun", "station": "Long Sight Base", "unlock": "Viajar 300 al desde el inicio y entregar 3 reliquias de Soontill.", "specialties": "MDD, escudos y propulsores"},
    "The Dweller": {"system": "Wyrd", "station": "Black Hide", "unlock": "Comerciar en 5 mercados negros y pagar 500.000 CR.", "specialties": "Distribuidores y láseres"},
    "Tod 'The Blaster' McQuinn": {"system": "Wolf 397", "station": "Trophy Camp", "unlock": "Cobrar 15 bonos de recompensa y entregar 100.000 CR en bonos.", "specialties": "Multicañones, cañones y fragmentación"},
    "Selene Jean": {"system": "Kuk", "station": "Prospector's Rest", "unlock": "Minar 500 t y entregar 10 t de painita.", "specialties": "Blindaje y refuerzos de casco"},
    "Marco Qwent": {"system": "Sirius", "station": "Qwent Research Base", "unlock": "Permiso de Sirius y entrega de 25 terminales modulares.", "specialties": "Plantas de energía y distribuidores"},
    "Professor Palin": {"system": "Arque", "station": "Abel Laboratory", "unlock": "Viajar 5.000 al y entregar 25 fragmentos de sensor Thargoide.", "specialties": "Propulsores y resistencia a corrosión"},
    "Chloe Sedesi": {"system": "Shenve", "station": "Cinder Dock", "unlock": "Viajar 5.000 al y entregar 25 fragmentos de sensor Thargoide.", "specialties": "Propulsores y MDD"},
    "Lei Cheung": {"system": "Laksak", "station": "Trader's Rest", "unlock": "Comerciar en 50 mercados y entregar 200 t de oro.", "specialties": "Escudos y potenciadores"},
    "Didi Vatermann": {"system": "Leesti", "station": "Vatermann LLC", "unlock": "Alcanzar Comerciante y entregar 50 t de Lavian Brandy.", "specialties": "Potenciadores de escudo"},
    "Liz Ryder": {"system": "Eurybia", "station": "Demolition Unlimited", "unlock": "Reputación con Eurybia Blue Mafia y entregar 200 t de minas terrestres.", "specialties": "Misiles, torpedos y blindaje"},
    "Hera Tani": {"system": "Kuwemaki", "station": "The Jet's Hole", "unlock": "Rango Forastero imperial y entregar 50 t de Kamitra Cigars.", "specialties": "Plantas, distribuidores y sensores"},
    "Broo Tarquin": {"system": "Muang", "station": "Broo's Legacy", "unlock": "Rango Competente de combate y entregar 50 t de Fujin Tea.", "specialties": "Armas láser"},
    "Bill Turner": {"system": "Alioth", "station": "Turner Metallics Inc", "unlock": "Permiso de Alioth y entregar 50 t de bromelita.", "specialties": "Plasma, sensores y utilidades"},
    "Juri Ishmaak": {"system": "Giryak", "station": "Pater's Memorial", "unlock": "Cobrar 50 bonos de combate y entregar 100.000 CR en bonos.", "specialties": "Minas, misiles y sensores"},
    "Tiana Fortune": {"system": "Achenar", "station": "Fortune's Loss", "unlock": "Rango Amistoso imperial y entregar 50 t de decodificadores HN.", "specialties": "Sensores, escáneres y drones"},
    "Ram Tah": {"system": "Meene", "station": "Phoenix Base", "unlock": "Alcanzar Topógrafo y entregar 50 unidades de datos escaneados.", "specialties": "Escáneres, defensas y sistemas Guardian"},
    "Lori Jameson": {"system": "Shinrarta Dezhra", "station": "Jameson Base", "unlock": "Rango Peligroso y acceso a Shinrarta Dezhra.", "specialties": "Sensores, escáneres y soporte"},
    "Zacariah Nemo": {"system": "Yoru", "station": "Nemo Cyber Party Base", "unlock": "Invitación de Party of Yoru y entregar 25 t de Xihe Biomorphic Companions.", "specialties": "Fragmentación y plasma"},
    "Petra Olmanova": {"system": "Asura", "station": "Sanctuary", "unlock": "Acceso mediante los ingenieros de Colonia y entrega requerida por el taller.", "specialties": "Blindaje, casco y armas"},
    "Mel Brandon": {"system": "Luchtaine", "station": "The Brig", "unlock": "Acceso mediante la cadena de Colonia y bonos de recompensa.", "specialties": "Escudos, MDD, armas y propulsores"},
    "Marsha Hicks": {"system": "Tir", "station": "The Watchtower", "unlock": "Acceso mediante la cadena de Colonia y entrega minera.", "specialties": "Armas, limpets, refinerías y minería"},
    "Etienne Dorn": {"system": "Los", "station": "Kraken's Retreat", "unlock": "Acceso mediante la cadena de Colonia y muestras biológicas.", "specialties": "Soporte vital, sensores y refuerzos"},
}

ENGINEER_VOICE_ALIASES = {
    "marco cuenta": "Marco Qwent", "marco cuent": "Marco Qwent",
    "marco cuen": "Marco Qwent", "marco quen": "Marco Qwent",
    "felicidad farseer": "Felicity Farseer", "felicity farcir": "Felicity Farseer",
    "elvira martuk": "Elvira Martuuk", "profesor palin": "Professor Palin",
    "el habitante": "The Dweller", "the dweler": "The Dweller",
}


def _spoken_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def engineer_name_candidates(value: str, extra_aliases: dict[str, str] | None = None) -> tuple[tuple[str, float], ...]:
    """Devuelve candidatos únicos ordenados por semejanza fonética textual."""

    spoken = _spoken_name(value)
    if not spoken:
        return ()
    aliases = {_spoken_name(name): name for name in ENGINEERS}
    aliases.update(ENGINEER_VOICE_ALIASES)
    aliases.update({_spoken_name(key): value for key, value in (extra_aliases or {}).items()
                    if value in ENGINEERS})
    best_by_name: dict[str, float] = {}
    for candidate, name in aliases.items():
        score = SequenceMatcher(None, spoken, candidate).ratio()
        best_by_name[name] = max(score, best_by_name.get(name, 0.0))
    return tuple(sorted(best_by_name.items(), key=lambda item: item[1], reverse=True))


def resolve_engineer_name(value: str, extra_aliases: dict[str, str] | None = None) -> str | None:
    """Resuelve nombres dictados sin permitir una coincidencia ambigua."""

    spoken = _spoken_name(value)
    if not spoken:
        return None
    aliases = {_spoken_name(name): name for name in ENGINEERS}
    aliases.update(ENGINEER_VOICE_ALIASES)
    aliases.update({_spoken_name(key): name for key, name in (extra_aliases or {}).items()
                    if name in ENGINEERS})
    if spoken in aliases:
        return aliases[spoken]
    ranked = sorted(
        ((SequenceMatcher(None, spoken, candidate).ratio(), name)
         for candidate, name in aliases.items()), reverse=True
    )
    if not ranked or ranked[0][0] < 0.68:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08:
        return None
    return ranked[0][1]


def normalize_engineering_objective(objective: str, extra_aliases: dict[str, str] | None = None) -> str:
    """Canoniza objetivos naturales como «quiero desbloquear a Marco Cuenta»."""

    clean = " ".join(str(objective or "").strip().split())
    match = re.search(
        r"\b(?:quiero\s+)?(?:desbloquear|desbloquea|desbloqueá|habilitar|liberar)\s+"
        r"(?:a\s+|al\s+)?(?:el\s+|la\s+)?(?:ingeniero|ingeniera)?\s*(?P<name>.+)$",
        clean, flags=re.IGNORECASE,
    )
    if not match:
        return clean
    spoken_name = match.group("name").strip(" ,.;:!?\"")
    resolved = resolve_engineer_name(spoken_name, extra_aliases)
    return f"desbloquear al ingeniero {resolved or spoken_name}"


def _plan(label: str, engineer: str, blueprint: str, materials: dict) -> dict:
    return {"label": label, "engineer": engineer, "blueprint": blueprint,
            "grade": 5, "materials": materials}


# Materiales de una fabricación G5. El consumo real siempre lo confirma el Journal.
ENGINEERING_PLANS = {
    "fsd_range_g5": _plan("MDD · Mayor alcance G5", "Felicity Farseer", "FSD_LongRange", {"arsenic": ("Arsénico", 1), "chemicalmanipulators": ("Manipuladores químicos", 1), "dataminedwake": ("Excepciones en análisis de estelas", 1)}),
    "thrusters_dirty_g5": _plan("Propulsores · Sucios G5", "Professor Palin", "Engine_Dirty", {"cadmium": ("Cadmio", 1), "pharmaceuticalisolators": ("Aislantes farmacéuticos", 1), "decodedemissiondata": ("Datos de emisión descodificados", 1)}),
    "powerplant_armoured_g5": _plan("Planta · Blindada G5", "Marco Qwent", "PowerPlant_Armoured", {"tungsten": ("Tungsteno", 1), "militarygradealloys": ("Aleaciones de grado militar", 1), "heatvanes": ("Palas térmicas", 1)}),
    "powerplant_overcharged_g5": _plan("Planta · Sobrecargada G5", "Hera Tani", "PowerPlant_Overcharged", {"cadmium": ("Cadmio", 1), "exquisitefocuscrystals": ("Cristales de enfoque exquisitos", 1), "securityfirmware": ("Firmware de seguridad", 1)}),
    "shield_reinforced_g5": _plan("Escudo · Reforzado G5", "Lei Cheung", "ShieldGenerator_Reinforced", {"antimony": ("Antimonio", 1), "improvisedcomponents": ("Componentes improvisados", 1), "exquisitefocuscrystals": ("Cristales de enfoque exquisitos", 1)}),
    "shield_thermal_g5": _plan("Escudo · Resistencia térmica G5", "Lei Cheung", "ShieldGenerator_Thermic", {"selenium": ("Selenio", 1), "conductiveceramics": ("Cerámicas conductivas", 1), "refinedfocuscrystals": ("Cristales de enfoque refinados", 1)}),
    "weapon_overcharged_g5": _plan("Arma · Sobrecargada G5", "Tod 'The Blaster' McQuinn", "Weapon_Overcharged", {"zirconium": ("Circonio", 1), "militarygradealloys": ("Aleaciones de grado militar", 1), "securityfirmware": ("Firmware de seguridad", 1)}),
    "weapon_efficient_g5": _plan("Arma · Eficiente G5", "Broo Tarquin", "Weapon_Efficient", {"heatvanes": ("Palas térmicas", 1), "protolightalloys": ("Protoaleaciones ligeras", 1), "scrambledemissiondata": ("Transmisiones codificadas excepcionales", 1)}),
}


class EngineeringTracker:
    EVENTS = ("EngineerProgress", "Materials", "MaterialCollected", "MaterialDiscarded",
              "MaterialTrade", "MissionCompleted", "EngineerCraft", "Loadout")

    def __init__(self, plan_path: Path) -> None:
        self.plan_path = plan_path
        self.materials: dict[str, int] = {}
        self.engineers: dict[str, dict] = {}
        self.modules: tuple[dict, ...] = ()
        self.last_craft: dict = {}
        self.selected_plan = self._load_plan()
        self.voice_alias_path = self.plan_path.with_name("voice_aliases.json")
        self.voice_aliases = self._load_voice_aliases()

    def resolve_engineer(self, spoken_name: str) -> str | None:
        return resolve_engineer_name(spoken_name, self.voice_aliases)

    def engineer_candidates(self, spoken_name: str) -> tuple[tuple[str, float], ...]:
        return engineer_name_candidates(spoken_name, self.voice_aliases)

    def learn_voice_alias(self, spoken_name: str, engineer: str) -> bool:
        alias = _spoken_name(spoken_name)
        if not alias or engineer not in ENGINEERS:
            return False
        self.voice_aliases[alias] = engineer
        self.voice_alias_path.parent.mkdir(parents=True, exist_ok=True)
        self.voice_alias_path.write_text(
            json.dumps(self.voice_aliases, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    def _load_voice_aliases(self) -> dict[str, str]:
        try:
            payload = json.loads(self.voice_alias_path.read_text(encoding="utf-8"))
            return {_spoken_name(key): str(value) for key, value in payload.items()
                    if str(value) in ENGINEERS and _spoken_name(key)}
        except (OSError, ValueError, TypeError, AttributeError):
            return {}

    @staticmethod
    def _name(value) -> str:
        return re.sub(r"[^a-z0-9_]", "", str(value or "").casefold().strip("$;"))

    def _adjust(self, name, delta) -> None:
        key = self._name(name)
        if key:
            self.materials[key] = max(0, self.materials.get(key, 0) + int(delta or 0))

    def handle(self, event: dict) -> None:
        kind = str(event.get("event", ""))
        if kind == "EngineerProgress":
            for item in event.get("Engineers", ()) or ():
                name = str(item.get("Engineer", "") or "").strip()
                if name:
                    self.engineers[name] = {"status": str(item.get("Progress", "Unknown") or "Unknown"), "rank": int(item.get("Rank", 0) or 0), "rank_progress": int(item.get("RankProgress", 0) or 0)}
        elif kind == "Materials":
            self.materials = {self._name(item.get("Name")): max(0, int(item.get("Count", 0) or 0)) for category in ("Raw", "Manufactured", "Encoded") for item in (event.get(category, ()) or ()) if self._name(item.get("Name"))}
        elif kind in {"MaterialCollected", "MaterialDiscarded"}:
            self._adjust(event.get("Name"), int(event.get("Count", 0) or 0) * (1 if kind == "MaterialCollected" else -1))
        elif kind == "MaterialTrade":
            for field, sign in (("Paid", -1), ("Received", 1)):
                item = event.get(field, {}) or {}; self._adjust(item.get("Material"), sign * int(item.get("Quantity", 0) or 0))
        elif kind == "MissionCompleted":
            for item in event.get("MaterialsReward", ()) or ():
                self._adjust(item.get("Name"), item.get("Count", 0))
        elif kind == "EngineerCraft":
            for item in event.get("Ingredients", ()) or ():
                self._adjust(item.get("Name"), -int(item.get("Count", 0) or 0))
            self.last_craft = {"engineer": event.get("Engineer", ""), "blueprint": event.get("BlueprintName", ""), "grade": int(event.get("Level", 0) or 0)}
        elif kind == "Loadout":
            modules = []
            for item in event.get("Modules", ()) or ():
                engineering = item.get("Engineering", {}) or {}
                if engineering:
                    modules.append({"slot": item.get("Slot", ""), "module": item.get("Item", ""), "engineer": engineering.get("Engineer", ""), "blueprint": engineering.get("BlueprintName", ""), "grade": int(engineering.get("Level", 0) or 0), "experimental": engineering.get("ExperimentalEffect_Localised", engineering.get("ExperimentalEffect", ""))})
            self.modules = tuple(modules)

    def select_plan(self, plan_key: str) -> bool:
        if plan_key not in ENGINEERING_PLANS:
            return False
        self.selected_plan = plan_key
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(json.dumps({"plan_key": plan_key}, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def _load_plan(self) -> str:
        try:
            key = str(json.loads(self.plan_path.read_text(encoding="utf-8")).get("plan_key", ""))
            return key if key in ENGINEERING_PLANS else ""
        except (OSError, ValueError, TypeError):
            return ""

    def snapshot(self) -> dict:
        engineers = {name: {**ENGINEERS.get(name, {}), **self.engineers.get(name, {"status": "Unknown", "rank": 0, "rank_progress": 0})} for name in sorted(set(ENGINEERS) | set(self.engineers))}
        plans = {}
        for key, plan in ENGINEERING_PLANS.items():
            requirements = []
            for material, (label, required) in plan["materials"].items():
                available = int(self.materials.get(material, 0)); missing = max(0, required - available)
                requirements.append({"material": material, "label": label, "required": required, "available": available, "missing": missing})
            plans[key] = {**plan, "requirements": tuple(requirements), "complete": all(not item["missing"] for item in requirements)}
        return {"engineers": engineers, "plans": plans, "selected_plan": self.selected_plan, "modules": self.modules, "last_craft": dict(self.last_craft)}
