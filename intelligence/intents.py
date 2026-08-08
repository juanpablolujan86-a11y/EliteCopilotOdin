"""Intenciones ejecutables reconocidas sin delegar acciones al modelo de lenguaje."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NeutronRouteIntent:
    destination: str


@dataclass(frozen=True, slots=True)
class HomeRouteIntent:
    pass

def _normalize_voice_text(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    plain = re.sub(r"\ba\s*cass?a\b|\bacass?a\b", "a casa", plain)
    plain = re.sub(r"\b(?:jevame|yevame)\b", "llevame", plain)
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def parse_home_route_intent(text: str) -> HomeRouteIntent | None:
    lowered = _normalize_voice_text(text)
    home = re.search(r"\b(?:casa|base)\b", lowered)
    movement = re.search(
        r"\b(?:vamos|vamo|ir|viaj|ruta|llev|regres|volv|dorme)", lowered
    )
    return HomeRouteIntent() if home and movement else None


def parse_neutron_route_intent(text: str) -> NeutronRouteIntent | None:
    lowered = text.casefold()
    navigation_words = ("ruta", "viaj", "ir ", "llev", "calcul", "planific", "traz")
    if "neutron" not in lowered and not any(word in lowered for word in navigation_words):
        return None

    patterns = (
        r"neutrones?\s+(?:hasta|a)\s+(?P<destination>.+)$",
        r"(?:hasta|al\s+sistema)\s+(?P<destination>.+?)(?:\s+por\s+(?:la\s+)?ruta|\s+usando|\s+mediante|$)",
        r"(?:viajar|viaje|ir|llevarme)\s+a\s+(?P<destination>.+?)(?:\s+por\s+(?:la\s+)?ruta|\s+usando|\s+mediante|$)",
    )
    destination = ""
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            destination = match.group("destination").strip(" \t,.;:!?\"'")
            break
    destination = re.sub(r"\s+(?:de\s+)?neutrones?$", "", destination, flags=re.IGNORECASE)
    if not destination or destination.casefold() in {
        "algún sistema", "un sistema", "la burbuja", "algún sistema de la burbuja"
    }:
        return None
    return NeutronRouteIntent(destination)
