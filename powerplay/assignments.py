"""Asignaciones semanales Powerplay: clasificación, persistencia y progreso."""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(slots=True)
class WeeklyAssignment:
    assignment_id: str
    description: str
    activity: str
    required: int = 0
    progress: int = 0
    destination_system: str = ""
    destination_station: str = ""
    status: str = "active"
    source: str = "journal"
    cycle_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


KEYWORDS = {
    "megaship": ("megaship", "megabuque", "meganave", "datalink", "enlace de datos"),
    "combat": ("kill", "destroy", "bounty", "mata", "destruye", "recompensa"),
    "mining": ("mined", "mining", "mina", "mineral", "extrae"),
    "trade": ("sell", "profit", "rare", "vende", "beneficio", "raro"),
    "transport": ("deliver", "transport", "supply", "entrega", "transporta", "suministro"),
    "exploration": ("cartographic", "exploration data", "cartografía", "datos de exploración"),
    "on_foot": ("settlement", "malware", "holoscreen", "asentamiento", "pantalla holográfica"),
    "salvage": ("salvage", "recover", "recupera", "escape pod", "rescue",
                "salvamento", "cápsula", "rescate"),
    "crime": ("commit crime", "fine", "bounty on yourself", "comete delitos", "multa"),
}


def classify_assignment(description: str) -> str:
    text = " ".join(str(description).casefold().split())
    for activity, words in KEYWORDS.items():
        if any(re.search(
            r"(?<!\w)" + re.escape(word).replace(r"\ ", r"\s+")
            + r"(?:s|es)?(?!\w)",
            text,
        ) for word in words):
            return activity
    return "unknown"


def assignment_from_text(
    description: str, *, assignment_id: str = "", source: str = "text",
    cycle_id: str = "",
) -> WeeklyAssignment:
    clean = " ".join(str(description).split())
    counter = re.search(r"\b(\d+)\s*/\s*(\d+)\b", clean)
    amount = re.search(r"\b(\d[\d., ]*)\b", clean)
    required = (
        int(counter.group(2)) if counter
        else int(re.sub(r"\D", "", amount.group(1))) if amount else 0
    )
    progress = int(counter.group(1)) if counter else 0
    digest = hashlib.sha256(clean.casefold().encode("utf-8")).hexdigest()[:16]
    cycle = cycle_id or powerplay_cycle_id()
    stable_id = assignment_id or f"weekly-{cycle}-{digest}"
    return WeeklyAssignment(
        stable_id, clean, classify_assignment(clean), required=required,
        progress=progress,
        source=source, cycle_id=cycle,
    )


def powerplay_cycle_id(now: datetime | None = None) -> str:
    """Identifica el ciclo iniciado el jueves a las 07:00 UTC."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    days_since_thursday = (current.weekday() - 3) % 7
    boundary = (current - timedelta(days=days_since_thursday)).replace(
        hour=7, minute=0, second=0, microsecond=0,
    )
    if current < boundary:
        boundary -= timedelta(days=7)
    return boundary.date().isoformat()


class WeeklyAssignmentStore:
    def __init__(self, data_root: Path) -> None:
        self.path = Path(data_root) / "powerplay" / "weekly_assignments.json"

    def load(self) -> list[WeeklyAssignment]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            current_cycle = powerplay_cycle_id()
            assignments = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                assignment = WeeklyAssignment(**item)
                # Compatibilidad con cachés creadas antes de guardar el ciclo.
                if not assignment.cycle_id:
                    assignment.cycle_id = current_cycle
                if assignment.cycle_id == current_cycle:
                    assignments.append(assignment)
            return assignments
        except (OSError, ValueError, TypeError):
            return []

    def save(self, assignments) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(
            [item.to_dict() for item in assignments], ensure_ascii=False, indent=2
        ), encoding="utf-8")
        temporary.replace(self.path)

    def ingest_mission(self, event: dict) -> WeeklyAssignment | None:
        name = str(event.get("Name", ""))
        description = str(event.get("LocalisedName", name))
        combined = f"{name} {description}".casefold()
        if "powerplay" not in combined and "power play" not in combined:
            return None
        assignment = assignment_from_text(
            description, assignment_id=str(event.get("MissionID", "")),
            source="journal",
        )
        assignment.destination_system = str(event.get("DestinationSystem", "") or "")
        assignment.destination_station = str(event.get("DestinationStation", "") or "")
        assignments = {item.assignment_id: item for item in self.load()}
        assignments[assignment.assignment_id] = assignment
        self.save(assignments.values())
        return assignment

    def complete(self, assignment_id: str) -> bool:
        return self.set_status(assignment_id, "completed", complete_progress=True)

    def set_status(
        self, assignment_id: str, status: str, *, complete_progress: bool = False,
    ) -> bool:
        assignments = self.load()
        changed = False
        for item in assignments:
            if item.assignment_id == str(assignment_id):
                item.status = str(status)
                if complete_progress:
                    item.progress = max(item.progress, item.required)
                changed = True
        if changed:
            self.save(assignments)
        return changed

    def update_progress(
        self, assignment_id: str, progress: int, required: int | None = None,
    ) -> bool:
        assignments = self.load()
        changed = False
        for item in assignments:
            if item.assignment_id != str(assignment_id):
                continue
            item.progress = max(0, int(progress))
            if required is not None and int(required) > 0:
                item.required = int(required)
            if item.required > 0 and item.progress >= item.required:
                item.status = "completed"
            changed = True
        if changed:
            self.save(assignments)
        return changed


SOLUTION_STEPS = {
    "megaship": (
        "Buscá un megabuque dentro del territorio requerido.",
        "Entrá en su instancia y selecciónalo en Contactos.",
        "Usá el escáner de enlace de datos hasta completar el escaneo.",
    ),
    "combat": (
        "Confirmá en Actividades locales qué objetivos cuentan.",
        "Combatí únicamente naves identificadas para la potencia o recompensa requerida.",
        "Verificá el avance antes de abandonar el sistema.",
    ),
    "trade": (
        "Confirmá mercancía, territorio y porcentaje de beneficio exigido.",
        "Comprá fuera del destino cuando la asignación lo requiera.",
        "Vendé primero una unidad y comprobá el avance antes de entregar el resto.",
    ),
    "mining": (
        "Extraé el mineral en el sistema de origen requerido.",
        "Conservá la trazabilidad desde la refinería; no uses carga comprada o de carrier.",
        "Vendé una unidad de prueba y confirmá el progreso antes del lote completo.",
    ),
    "transport": (
        "Retirá la mercancía asignada desde un Contacto Powerplay válido.",
        "Llevála al tipo de territorio indicado por la asignación.",
        "Entregala en el Contacto Powerplay y verificá el progreso.",
    ),
    "exploration": (
        "Recolectá cartografía válida; la exobiología no es equivalente.",
        "Viajá a una estación elegible con Universal Cartographics.",
        "Vendé un sistema individual y confirmá el avance antes del resto.",
    ),
    "on_foot": (
        "Confirmá territorio, tipo de asentamiento y dato u objeto exacto.",
        "Prepará traje, herramientas y nivel de acceso antes de aterrizar.",
        "Completá la acción y entregá el objetivo donde indique la asignación.",
    ),
    "salvage": (
        "Confirmá qué objeto de salvamento cuenta y dónde debe recogerse.",
        "No mezcles objetos de carrier o adquiridos por otro método.",
        "Entregá una unidad y comprobá el avance antes del resto.",
    ),
    "crime": (
        "Revisá exactamente qué delito exige la asignación y en qué territorio.",
        "Comprobá multas, recompensa y notoriedad antes de continuar.",
        "Detenete al alcanzar el objetivo para evitar consecuencias adicionales.",
    ),
}


def assignment_solution(assignment: WeeklyAssignment) -> dict:
    steps = SOLUTION_STEPS.get(assignment.activity, (
        "Abrí el detalle de la asignación y confirmá su objetivo exacto.",
    ))
    return {
        "assignment_id": assignment.assignment_id,
        "activity": assignment.activity,
        "destination_system": assignment.destination_system,
        "destination_station": assignment.destination_station,
        "required": assignment.required,
        "progress": assignment.progress,
        "steps": list(steps),
        "needs_location_search": not bool(assignment.destination_system),
    }


SEARCH_ACTIVITY = {
    "combat": "combat", "crime": "combat", "trade": "trade",
    "mining": "mining", "transport": "transport",
    "exploration": "exploration", "on_foot": "on_foot",
    "salvage": "salvage",
}


def assignment_search_request(assignment: WeeklyAssignment) -> dict:
    """Decide si hay información suficiente para buscar un destino fiable."""

    if assignment.destination_system:
        return {"eligible": False, "activity": "", "subject": "",
                "reason": "La asignación ya incluye un sistema de destino."}
    activity = SEARCH_ACTIVITY.get(assignment.activity, "")
    if not activity:
        return {
            "eligible": False, "activity": "", "subject": "",
            "reason": ("Esta actividad necesita una ubicación visible en el juego; "
                       "no es seguro inferirla sólo con territorios comunitarios."),
        }
    subject = ""
    if activity in {"trade", "mining"}:
        match = re.search(
            r"\b(?:de|of)\b\s+([\wÀ-ÿ' -]{3,40}?)(?:\s+(?:en|in|a|to)\s+|$)",
            assignment.description, re.IGNORECASE,
        )
        subject = " ".join(match.group(1).split()) if match else ""
        if any(character.isdigit() for character in subject):
            subject = ""
        generic = {"mineral", "minerales", "mineral extraído",
                   "minerales extraídos", "mercancía", "mercancías",
                   "commodity", "commodities"}
        if subject.casefold() in generic:
            subject = ""
        if not subject:
            return {
                "eligible": False, "activity": activity, "subject": "",
                "reason": ("La asignación no identifica el producto o mineral exacto. "
                           "Indicá ese dato en la pestaña Powerplay para buscarlo."),
            }
    return {"eligible": True, "activity": activity, "subject": subject,
            "reason": ""}
