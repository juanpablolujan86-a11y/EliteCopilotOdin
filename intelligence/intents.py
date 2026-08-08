"""Intenciones ejecutables reconocidas sin delegar acciones al modelo de lenguaje."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NeutronRouteIntent:
    destination: str


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
