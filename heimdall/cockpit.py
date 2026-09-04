"""Estado y solicitudes informativas de asistencia de cabina."""

from __future__ import annotations

import re
from dataclasses import dataclass

from heimdall.bindings import BindingAction, BindingAudit
from core.localization import text as localized_text

LIGHTS_ON = 0x00000100
NIGHT_VISION_ON = 0x10000000
CARGO_SCOOP_DEPLOYED = 0x00000200
IN_MAIN_SHIP = 0x01000000
IN_SRV = 0x04000000
DOCKED = 0x00000001
LANDED = 0x00000002
SUPERCRUISE = 0x00000010
LANDING_GEAR_DOWN = 0x00000004


@dataclass(frozen=True, slots=True)
class CockpitState:
    known: bool = False
    in_main_ship: bool = False
    in_srv: bool = False
    docked: bool = False
    landed: bool = False
    in_supercruise: bool = False
    lights_on: bool = False
    night_vision_on: bool = False
    landing_gear_down: bool = False
    gui_focus: int = 0
    cargo_scoop_deployed: bool = False

    @classmethod
    def from_status(cls, status: dict) -> "CockpitState":
        if "Flags" not in status:
            return cls()
        flags = int(status.get("Flags", 0))
        return cls(
            known=True,
            in_main_ship=bool(flags & IN_MAIN_SHIP),
            in_srv=bool(flags & IN_SRV),
            docked=bool(flags & DOCKED),
            landed=bool(flags & LANDED),
            in_supercruise=bool(flags & SUPERCRUISE),
            lights_on=bool(flags & LIGHTS_ON),
            night_vision_on=bool(flags & NIGHT_VISION_ON),
            landing_gear_down=bool(flags & LANDING_GEAR_DOWN),
            gui_focus=int(status.get("GuiFocus", 0) or 0),
            cargo_scoop_deployed=bool(flags & CARGO_SCOOP_DEPLOYED),
        )


@dataclass(frozen=True, slots=True)
class CockpitIntent:
    feature: str
    requested_state: bool | None


def parse_cockpit_intent(text: str) -> CockpitIntent | None:
    lowered = text.casefold()
    # Whisper puede devolver las formas portuguesas con o sin diacríticos.
    lowered_plain = lowered.translate(str.maketrans("ãç", "ac"))
    if re.search(
        r"\b(?:solicita|solicitá|pide|pedí|pedi|request|ask|solicitar|pedir)\b.*"
        r"\b(?:aterrizaje|atraque|aterrizar|atracar|docking|landing|atracacao|atracação|pouso)\b",
        lowered,
    ) or re.search(r"\b(?:permiso|autorización|autorizacion)\s+(?:de|para)\s+(?:aterrizaje|atraque|aterrizar|atracar)\b", lowered):
        return CockpitIntent("docking_request", True)
    srv_mentioned = bool(
        re.search(r"\b(?:srv|vrs|scarab|veh[ií]culo)\b", lowered)
    )
    if srv_mentioned and re.search(r"\b(?:(?:vision|visión|visao|luz)\s+(?:nocturna|noturna)|night\s+vision)\b", lowered_plain):
        feature = "srv_night_vision"
    elif srv_mentioned and re.search(
        r"\b(?:colector|coletor|compuerta)\s+(?:de\s+)?carga\b|\bcargo\s+scoop\b",
        lowered,
    ):
        feature = "srv_cargo_scoop"
    elif srv_mentioned and re.search(r"\b(?:luces|faros|luz)\b", lowered):
        feature = "srv_lights"
    elif re.search(r"\b(?:(?:vision|visión|visao|luz)\s+(?:nocturna|noturna)|night\s+vision)\b", lowered_plain):
        feature = "night_vision"
    elif re.search(
        r"\b(?:colector|coletor|compuerta)\s+(?:de\s+)?carga\b|\bcargo\s+scoop\b",
        lowered,
    ):
        feature = "cargo_scoop"
    elif re.search(
        r"\b(?:tren[d]?|tres?)\s+(?:(?:de\s+)?aterrizaje)|"
        r"\btren\b|\blanding\s+gear\b|\btrem\s+de\s+pouso\b",
        lowered,
    ):
        feature = "landing_gear"
    elif re.search(
        r"\b(?:hipersalto|hiper\s+salto|salto\s+hiperespacial|"
        r"salto\s+al\s+hiperespacio|hyperspace(?:\s+jump)?|"
        r"salto\s+(?:no|ao)\s+hiperespaco|salto\s+(?:no|ao)\s+hiperespaço)\b",
        lowered,
    ):
        return CockpitIntent("hyperspace", True)
    elif re.search(r"\b(?:luces|luz)\b", lowered):
        feature = "lights"
    else:
        return None

    if re.search(r"\b(?:prende|prendé|enciende|encendé|activa|activá|abre|despliega|baja|turn\s+on|enable|activate|deploy|ligar|liga|ativar|ativa|baixar)\b", lowered):
        requested = True
    elif re.search(r"\b(?:apaga|apagá|desactiva|desactivá|cierra|repliega|sube|turn\s+off|disable|deactivate|retract|desligar|desliga|desativar|desativa|recolher)\b", lowered):
        requested = False
    else:
        requested = None
    return CockpitIntent(feature, requested)


class CockpitAdvisor:
    ACTIONS = {
        "lights": "ShipSpotLightToggle",
        "night_vision": "NightVisionToggle",
        "landing_gear": "LandingGearToggle",
        "cargo_scoop": "ToggleCargoScoop",
        "hyperspace": "HyperSuperCombination",
        "srv_lights": "HeadlightsBuggyButton",
        "srv_night_vision": "NightVisionToggle",
        "srv_cargo_scoop": "ToggleCargoScoop_Buggy",
    }
    def __init__(self, audit: BindingAudit | None = None, language: str = "es-419") -> None:
        self.audit = audit
        self.language = language
        self.state = CockpitState()

    def _t(self, key: str, **values) -> str:
        return localized_text(key, self.language, **values)

    def update_status(self, status: dict) -> CockpitState:
        self.state = CockpitState.from_status(status)
        return self.state

    def describe(self, intent: CockpitIntent) -> str:
        if intent.feature == "docking_request":
            return self._t("cockpit.docking_panel")
        label = self._t(f"cockpit.feature.{intent.feature}")
        state_key = "lights" if intent.feature == "lights" else "night"
        if not self.state.known:
            return self._t("cockpit.unknown_state", feature=label)
        current = (
            self.state.lights_on
            if intent.feature == "lights"
            else self.state.night_vision_on
        )
        if intent.requested_state is None:
            return self._t(f"cockpit.{state_key}.{'on' if current else 'off'}")
        if not self.state.in_main_ship:
            return self._t("cockpit.not_main_ship", feature=label)
        if current == intent.requested_state:
            return self._t(f"cockpit.{state_key}.already_{'on' if current else 'off'}")
        binding = self._binding(intent.feature)
        if binding is None:
            return self._t("cockpit.no_binding", feature=label)
        action = self._t("cockpit.turn_on" if intent.requested_state else "cockpit.turn_off")
        return self._t("cockpit.informative", binding=self._format_binding(binding),
                       action=action, feature=label)

    def _describe_docking_request(self) -> str:
        if not self.state.known:
            return self._t("cockpit.docking_unknown")
        if not self.state.in_main_ship:
            return self._t("cockpit.docking_not_ship")
        if self.state.docked:
            return self._t("cockpit.docking_already")
        if self.state.landed:
            return self._t("cockpit.docking_surface")
        if self.state.in_supercruise:
            return self._t("cockpit.docking_supercruise")
        binding = self._binding("docking_request")
        if binding is None:
            return self._t("cockpit.docking_no_binding")
        return self._t("cockpit.docking_informative",
                       binding=self._format_binding(binding))

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

    def _format_binding(self, action: BindingAction) -> str:
        value = action.primary if action.primary.configured else action.secondary
        parts = [key.removeprefix("Key_") for _, key in value.modifiers]
        parts.append(value.key.removeprefix("Key_"))
        return self._t("cockpit.binding_join").join(parts)
