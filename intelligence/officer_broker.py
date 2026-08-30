"""Puente de evidencia entre la IA de ODIN y sus oficiales especializados."""

from __future__ import annotations

import json
import re
import threading
from copy import deepcopy


class OfficerKnowledgeBroker:
    """Convierte el estado ya calculado por cada oficial en informes acotados."""

    MAX_LIST_ITEMS = 12
    MAX_TEXT = 18_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_consulted: tuple[str, ...] = ("ODIN",)

    @staticmethod
    def officers_for(question: str) -> tuple[str, ...]:
        text = str(question or "").casefold()
        rules = {
            "MÍMIR": r"\b(?:biolog|exobiolog|especie|planeta|escaneo|cartograf|muestra)",
            "HEIMDALL": r"\b(?:ruta|salto|viaj|destino|combustible|fsd|nave|estaci[oó]n|base|aterriz|atrac|plataforma)",
            "FREYJA": r"\b(?:comerci|mercado|compr|vend|precio|ganancia|mercanc|estaci[oó]n|plataforma)",
            "BROKK": r"\b(?:miner|mineral|refiner|bodega|asteroide|painita|platino)",
            "INGENIERÍA": r"\b(?:ingenier|desbloque|material|m[oó]dulo|mejora|modific)",
            "GUARDIAN": r"\b(?:guardian|guardi[aá]n|tecnomediador)",
            "POWERPLAY": r"\b(?:powerplay|m[eé]rito|potencia|refuerzo|undermining)",
        }
        selected = ["ODIN"]
        selected.extend(name for name, pattern in rules.items() if re.search(pattern, text))
        if len(selected) == 1:
            selected.append("HEIMDALL")
        return tuple(dict.fromkeys(selected))

    @classmethod
    def _compact(cls, value, depth: int = 0):
        if depth > 6:
            return "…"
        if isinstance(value, dict):
            return {
                str(key): cls._compact(item, depth + 1)
                for key, item in value.items()
                if item not in (None, "", (), [], {})
            }
        if isinstance(value, (list, tuple)):
            return [cls._compact(item, depth + 1)
                    for item in value[: cls.MAX_LIST_ITEMS]]
        return value

    def reports(self, dashboard: dict) -> dict:
        state = deepcopy(dashboard or {})
        return {
            "ODIN": self._compact({
                "commander": state.get("commander"), "credits": state.get("credits"),
                "system": state.get("system"), "body": state.get("body"),
                "ship": state.get("ship"), "ship_ident": state.get("ship_ident"),
                "network": state.get("network"), "expedition": state.get("expedition"),
            }),
            "MÍMIR": self._compact({"biology": state.get("biology"),
                                     "expedition": state.get("expedition")}),
            "HEIMDALL": self._compact({
                "system": state.get("system"), "community_status": state.get("community_status"),
                "ship": state.get("ship"), "fuel": state.get("fuel"),
                "fuel_capacity": state.get("fuel_capacity"), "jump_range": state.get("jump_range"),
                "fsd_health": state.get("fsd_health"), "route": state.get("route"),
                "exact_plotter": state.get("exact_plotter"), "high_energy": state.get("high_energy"),
            }),
            "FREYJA": self._compact(state.get("trade", {})),
            "BROKK": self._compact(state.get("mining", {})),
            "INGENIERÍA": self._compact(state.get("engineering", {})),
            "GUARDIAN": self._compact(state.get("guardian", {})),
            "POWERPLAY": self._compact(state.get("powerplay", {})),
        }

    def context(
        self, dashboard: dict, question: str = "",
        allowed_officers: set[str] | None = None,
    ) -> str:
        reports = self.reports(dashboard)
        selected = self.officers_for(question) if question else tuple(reports)
        if allowed_officers is not None:
            selected = tuple(
                name for name in selected
                if name in allowed_officers
            )
        with self._lock:
            self._last_consulted = selected
        payload = json.dumps(
            {name: reports.get(name, {}) for name in selected},
            ensure_ascii=False, default=str,
        )
        if len(payload) > self.MAX_TEXT:
            payload = payload[: self.MAX_TEXT] + "…"
        return (
            "INFORMES DE LOS OFICIALES DE ODIN (fuentes internas; un campo ausente "
            "significa que el oficial todavía no dispone de ese dato):\n" + payload
        )

    def snapshot(self) -> dict:
        with self._lock:
            return {"consulted_officers": self._last_consulted}
