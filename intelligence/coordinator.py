"""Coordinación consultiva entre oficiales, sin ejecutar acciones del juego."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


OFFICERS = {"ODIN", "MÍMIR", "HEIMDALL", "FREYJA", "BROKK"}
ALLOWED_ACTIONS = {
    "informar", "analizar", "recomendar", "calcular_ruta", "buscar_comercio",
    "buscar_mineria", "planificar_ingenieria", "verificar_materiales",
}


@dataclass(frozen=True, slots=True)
class PlanStep:
    officer: str
    action: str
    reason: str
    requires_authorization: bool = False


@dataclass(frozen=True, slots=True)
class AdvisoryPlan:
    objective: str
    summary: str
    steps: tuple[PlanStep, ...]
    created_at: str
    advisory_only: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


class IntelligenceCoordinator:
    """Pide un plan estructurado a la IA y aplica una lista blanca estricta."""

    def __init__(self, assistant=None, plan_path: Path | None = None) -> None:
        self.assistant = assistant
        self.plan_path = plan_path
        self.last_plan: AdvisoryPlan | None = self._load()

    @staticmethod
    def prompt(objective: str) -> str:
        return f"""Creá un plan consultivo para este objetivo: {objective}
Devolvé exclusivamente JSON válido con esta forma:
{{"summary":"...","steps":[{{"officer":"ODIN","action":"informar","reason":"...","requires_authorization":false}}]}}
Oficiales permitidos: {', '.join(sorted(OFFICERS))}.
Acciones permitidas: {', '.join(sorted(ALLOWED_ACTIONS))}.
Máximo 4 pasos. No ordenes pulsaciones, compras, ventas ni acciones dentro del juego."""

    def propose(self, objective: str, context: str = "") -> AdvisoryPlan:
        objective = str(objective or "").strip()
        if not objective:
            raise ValueError("El objetivo de la IA no puede estar vacío.")
        if self.assistant is None:
            raise RuntimeError("No hay un proveedor de IA configurado.")
        reply = self.assistant.ask(self.prompt(objective), context=context)
        plan = self.parse(objective, reply.text)
        self.last_plan = plan
        self._save(plan)
        return plan

    def _save(self, plan: AdvisoryPlan) -> None:
        if self.plan_path is None:
            return
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(
            json.dumps(plan.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load(self) -> AdvisoryPlan | None:
        if self.plan_path is None:
            return None
        try:
            payload = json.loads(self.plan_path.read_text(encoding="utf-8"))
            steps = tuple(
                PlanStep(
                    officer=str(item["officer"]), action=str(item["action"]),
                    reason=str(item["reason"]),
                    requires_authorization=bool(item.get("requires_authorization", False)),
                )
                for item in payload.get("steps", ())
                if str(item.get("officer", "")) in OFFICERS
                and str(item.get("action", "")) in ALLOWED_ACTIONS
            )
            if not steps:
                return None
            return AdvisoryPlan(
                objective=str(payload.get("objective", "")),
                summary=str(payload.get("summary", "")), steps=steps[:4],
                created_at=str(payload.get("created_at", "")), advisory_only=True,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None

    @staticmethod
    def parse(objective: str, response: str) -> AdvisoryPlan:
        match = re.search(r"\{.*\}", str(response or ""), re.DOTALL)
        if not match:
            raise ValueError("La IA no devolvió un plan estructurado.")
        try:
            payload = json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("La IA devolvió un plan inválido.") from error
        steps = []
        for raw in (payload.get("steps", ()) or ())[:4]:
            officer = str(raw.get("officer", "")).upper().strip()
            action = str(raw.get("action", "")).casefold().strip()
            reason = str(raw.get("reason", "")).strip()
            if officer not in OFFICERS or action not in ALLOWED_ACTIONS or not reason:
                continue
            steps.append(PlanStep(officer, action, reason,
                                  bool(raw.get("requires_authorization", False))))
        if not steps:
            raise ValueError("La IA no propuso pasos seguros reconocibles.")
        return AdvisoryPlan(
            objective=str(objective).strip(),
            summary=str(payload.get("summary", "Plan consultivo de ODIN")).strip(),
            steps=tuple(steps),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def snapshot(self) -> dict:
        return self.last_plan.as_dict() if self.last_plan else {
            "objective": "", "summary": "Sin plan activo", "steps": (),
            "created_at": "", "advisory_only": True,
        }
