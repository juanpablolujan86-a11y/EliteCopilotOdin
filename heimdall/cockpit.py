"""Estado y solicitudes informativas de asistencia de cabina."""

from __future__ import annotations

import re
from dataclasses import dataclass

from heimdall.bindings import BindingAction, BindingAudit

LIGHTS_ON = 0x00000100
NIGHT_VISION_ON = 0x10000000
IN_MAIN_SHIP = 0x01000000


@dataclass(frozen=True, slots=True)
class CockpitState:
    known: bool = False
    in_main_ship: bool = False
    lights_on: bool = False
    night_vision_on: bool = False

    @classmethod
    def from_status(cls, status: dict) -> "CockpitState":
        if "Flags" not in status:
            return cls()
        flags = int(status.get("Flags", 0))
        return cls(
            known=True,
            in_main_ship=bool(flags & IN_MAIN_SHIP),
            lights_on=bool(flags & LIGHTS_ON),
            night_vision_on=bool(flags & NIGHT_VISION_ON),
        )


@dataclass(frozen=True, slots=True)
class CockpitIntent:
    feature: str
    requested_state: bool | None


def parse_cockpit_intent(text: str) -> CockpitIntent | None:
    lowered = text.casefold()
    if re.search(r"\b(?:vision|visión)\s+nocturna\b", lowered):
        feature = "night_vision"
    elif re.search(r"\b(?:luces|luz)\b", lowered):
        feature = "lights"
    else:
        return None

    if re.search(r"\b(?:prende|prendé|enciende|encendé|activa|activá)\b", lowered):
        requested = True
    elif re.search(r"\b(?:apaga|apagá|desactiva|desactivá)\b", lowered):
        requested = False
    else:
        requested = None
    return CockpitIntent(feature, requested)


class CockpitAdvisor:
    ACTIONS = {"lights": "ShipSpotLightToggle", "night_vision": "NightVisionToggle"}
    LABELS = {"lights": "luces", "night_vision": "visión nocturna"}

    def __init__(self, audit: BindingAudit | None = None) -> None:
        self.audit = audit
        self.state = CockpitState()

    def update_status(self, status: dict) -> CockpitState:
        self.state = CockpitState.from_status(status)
        return self.state

    def describe(self, intent: CockpitIntent) -> str:
        label = self.LABELS[intent.feature]
        subject = "Las luces" if intent.feature == "lights" else "La visión nocturna"
        adjective_on = "encendidas" if intent.feature == "lights" else "activada"
        adjective_off = "apagadas" if intent.feature == "lights" else "desactivada"
        if not self.state.known:
            return f"No tengo un estado fiable de {label}. No ejecutaré ninguna acción."
        current = (
            self.state.lights_on
            if intent.feature == "lights"
            else self.state.night_vision_on
        )
        if intent.requested_state is None:
            return f"{subject} está{'n' if intent.feature == 'lights' else ''} {adjective_on if current else adjective_off}."
        if not self.state.in_main_ship:
            return f"No confirmo que estés en la nave principal. No cambiaré {label}."
        if current == intent.requested_state:
            return f"{subject} ya está{'n' if intent.feature == 'lights' else ''} {adjective_on if current else adjective_off}."
        binding = self._binding(intent.feature)
        if binding is None:
            return f"No encontré una tecla configurada para {label}."
        action = "encender" if intent.requested_state else "apagar"
        return (
            f"Modo informativo: usaría {self._format_binding(binding)} para {action} "
            f"{label}, pero no enviaré ninguna pulsación."
        )

    def _binding(self, feature: str) -> BindingAction | None:
        if self.audit is None:
            return None
        action_name = self.ACTIONS[feature]
        active = {name.casefold() for name in self.audit.active_presets}
        profiles = sorted(
            self.audit.profiles,
            key=lambda profile: profile.path.stem.split(".")[0].casefold() not in active,
        )
        for profile in profiles:
            action = profile.actions.get(action_name)
            if action is not None and action.configured:
                return action
        return None

    @staticmethod
    def _format_binding(action: BindingAction) -> str:
        value = action.primary if action.primary.configured else action.secondary
        parts = [key.removeprefix("Key_") for _, key in value.modifiers]
        parts.append(value.key.removeprefix("Key_"))
        return " más ".join(parts)
