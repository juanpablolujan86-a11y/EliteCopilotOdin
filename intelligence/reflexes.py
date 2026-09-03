"""Clasificación local de órdenes inequívocas que no necesitan un LLM."""

from __future__ import annotations

import re
import threading
from collections import Counter
from dataclasses import dataclass, field

from heimdall.cockpit import parse_cockpit_intent
from intelligence.intents import parse_home_route_intent, parse_neutron_route_intent


@dataclass(frozen=True, slots=True)
class ReflexMatch:
    intent: str
    officer: str
    payload: dict[str, str] = field(default_factory=dict)


def is_trade_menu_request(text: str) -> bool:
    """Reconoce una solicitud explícita de iniciar el flujo de FREYJA."""

    normalized = re.sub(
        r"[^a-z0-9áéíóúüñ]+", " ", str(text or "").casefold()
    ).strip()
    normalized = re.sub(r"\bgase+r\b", "hacer", normalized)
    explicit_trade = "comerci" in normalized and any(
        word in normalized
        for word in (
            "freyja", "freya", "quiero", "hacer", "vamos", "deseo",
            "quero", "fazer", "want", "trade", "trading", "start",
        )
    )
    explicit_trade = explicit_trade or bool(re.search(
        r"\b(?:i\s+want\s+to\s+trade|let(?:\s+s|s)?\s+trade|start\s+trading|"
        r"quero\s+comerciar|vamos\s+comerciar|fazer\s+comercio)\b",
        normalized,
    ))
    buy_and_sell = bool(
        re.search(r"\bcompr(?:ar|o|amos)?\b", normalized)
        and re.search(r"\bvend(?:er|o|emos)?\b", normalized)
    )
    observed_whisper_alias = bool(
        re.search(r"\b(?:el\s+)?fin\s+de\s+la\s+proxima\s+vez\b", normalized)
        or re.search(r"\b(?:el\s+)?fin\s+de\s+la\s+próxima\s+vez\b", normalized)
        or normalized in {"vale bien", "y vale bien"}
    )
    return bool(explicit_trade or buy_and_sell or observed_whisper_alias)


class ReflexResolver:
    """Selecciona comandos locales rápidos y mantiene telemetría agregada."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resolved = 0
        self._missed = 0
        self._by_intent: Counter[str] = Counter()

    def resolve(self, text: str, *, record: bool = True) -> ReflexMatch | None:
        cockpit = parse_cockpit_intent(text)
        if cockpit is not None:
            if cockpit.feature == "docking_request":
                match = ReflexMatch("docking_request", "HEIMDALL")
            else:
                state = (
                    "toggle" if cockpit.requested_state is None
                    else "on" if cockpit.requested_state else "off"
                )
                match = ReflexMatch(
                    f"cockpit_{cockpit.feature}", "HEIMDALL", {"state": state}
                )
            self._record(match, record)
            return match
        if is_trade_menu_request(text):
            match = ReflexMatch("freyja_trade_menu", "FREYJA")
            self._record(match, record)
            return match
        if parse_home_route_intent(text) is not None:
            match = ReflexMatch("home_route", "HEIMDALL")
            self._record(match, record)
            return match
        route = parse_neutron_route_intent(text)
        if route is not None:
            match = ReflexMatch(
                "neutron_route", "HEIMDALL", {"destination": route.destination}
            )
            self._record(match, record)
            return match
        if record:
            with self._lock:
                self._missed += 1
        return None

    def _record(self, match: ReflexMatch, enabled: bool) -> None:
        if not enabled:
            return
        with self._lock:
            self._resolved += 1
            self._by_intent[match.intent] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "resolved": self._resolved,
                "missed": self._missed,
                "by_intent": dict(self._by_intent),
            }
