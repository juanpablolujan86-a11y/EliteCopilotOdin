"""Automatizacion conservadora de atraque para HEIMDALL en Windows."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from heimdall.bindings import BindingAction, BindingAudit, BindingInput
from heimdall.cockpit import CockpitState
from core.localization import text as localized_text


class WindowsEliteKeySender:
    """Envia una asignacion de teclado solamente a Elite en primer plano."""

    KEY_CODES = {
        **{f"Key_{chr(code)}": code for code in range(ord("A"), ord("Z") + 1)},
        **{f"Key_{number}": ord(str(number)) for number in range(10)},
        **{f"Key_F{number}": 0x6F + number for number in range(1, 13)},
        **{f"Key_Numpad_{number}": 0x60 + number for number in range(10)},
        "Key_Space": 0x20,
        "Key_Enter": 0x0D,
        "Key_Backspace": 0x08,
        "Key_LeftShift": 0xA0,
        "Key_RightShift": 0xA1,
        "Key_LeftControl": 0xA2,
        "Key_RightControl": 0xA3,
        "Key_LeftAlt": 0xA4,
        "Key_RightAlt": 0xA5,
    }
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    SCAN_CODES = {
        "Key_1": 0x02,
        "Key_A": 0x1E,
        "Key_D": 0x20,
        "Key_E": 0x12,
        "Key_L": 0x26,
        "Key_I": 0x17,
        "Key_J": 0x24,
        "Key_Home": 0x47,
        "Key_Q": 0x10,
        "Key_S": 0x1F,
        "Key_W": 0x11,
        "Key_Space": 0x39,
        "Key_Backspace": 0x0E,
        "Key_LeftShift": 0x2A,
        "Key_RightShift": 0x36,
        "Key_LeftControl": 0x1D,
        "Key_LeftAlt": 0x38,
    }
    EXTENDED_KEYS = {"Key_Home"}

    def elite_is_foreground(self) -> bool:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return False
        try:
            size = wintypes.DWORD(1024)
            path = ctypes.create_unicode_buffer(size.value)
            if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, path, ctypes.byref(size)
            ):
                return False
            return path.value.rsplit("\\", 1)[-1].casefold() == "elitedangerous64.exe"
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def send(self, binding: BindingInput) -> bool:
        if binding.device.casefold() != "keyboard" or not self.elite_is_foreground():
            return False
        key = self.SCAN_CODES.get(binding.key)
        modifiers = [self.SCAN_CODES.get(item_key) for _, item_key in binding.modifiers]
        if key is None or any(value is None for value in modifiers):
            return False
        for modifier in modifiers:
            if not self._send_scan_code(modifier, down=True):
                return False
        extended = binding.key in self.EXTENDED_KEYS
        if not self._send_scan_code(key, down=True, extended=extended):
            return False
        time.sleep(0.08)
        if not self._send_scan_code(key, down=False, extended=extended):
            return False
        for modifier in reversed(modifiers):
            self._send_scan_code(modifier, down=False)
        return True

    def _send_scan_code(
        self, scan_code: int, *, down: bool, extended: bool = False
    ) -> bool:
        class KeyboardInput(ctypes.Structure):
            _fields_ = (
                ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.WPARAM),
            )

        class MouseInput(ctypes.Structure):
            _fields_ = (
                ("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", wintypes.WPARAM),
            )

        class InputUnion(ctypes.Union):
            _fields_ = (("ki", KeyboardInput), ("mi", MouseInput))

        class Input(ctypes.Structure):
            _fields_ = (("type", wintypes.DWORD), ("value", InputUnion))

        flags = self.KEYEVENTF_SCANCODE | (self.KEYEVENTF_KEYUP if not down else 0)
        if extended:
            flags |= 0x0001
        item = Input(
            1,
            InputUnion(ki=KeyboardInput(0, scan_code, flags, 0, 0)),
        )
        return ctypes.windll.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(item)) == 1


class DockingAssist:
    """Decide acciones idempotentes usando Journal, Status y bindings reales."""

    def __init__(self, sender=None, language: str = "es-419") -> None:
        self.sender = sender or WindowsEliteKeySender()
        self.language = language
        self.enabled = False
        self.audit: BindingAudit | None = None
        self.state = CockpitState()
        self._last_action = ""
        self._last_action_at = 0.0

    def _t(self, key: str, **values) -> str:
        return localized_text(key, self.language, **values)

    def configure(self, *, enabled: bool, audit: BindingAudit | None) -> None:
        self.enabled = enabled
        self.audit = audit

    def update_status(self, state: CockpitState) -> None:
        self.state = state

    def handle_journal(self, event: dict) -> str | None:
        if not self.enabled:
            return None
        event_name = str(event.get("event", ""))
        if event_name in {"Undocked", "Liftoff"}:
            return self._set_gear(False)
        return None

    def request_station_docking(self) -> str:
        """Solicita atraque y restaura Navegacion usando los bindings de UI."""

        if not self.enabled:
            return self._t("docking.disabled")
        if not self.state.known or not self.state.in_main_ship:
            return self._t("docking.not_main_ship")
        if self.state.docked:
            return self._t("docking.already_docked")
        if self.state.landed:
            return self._t("docking.landed")
        if self.state.in_supercruise:
            return self._t("docking.supercruise")
        if self.state.gui_focus != 0:
            return self._t("docking.panel_open")

        sequence = (
            (("FocusLeftPanel",), 0.35),
            (("CycleNextPanel",) * 2, 0.20),
            (("UI_Right",), 0.20),
            (("UI_Select",), 0.45),
            (("CyclePreviousPanel",) * 2, 0.18),
            (("FocusLeftPanel",), 0.0),
        )
        required = {name for actions, _ in sequence for name in actions}
        bindings = {name: self._binding(name) for name in required}
        if any(binding is None for binding in bindings.values()):
            return self._t("docking.bindings_missing")
        for actions, pause in sequence:
            for action_name in actions:
                if not self.sender.send(bindings[action_name]):
                    return self._t("docking.send_failed")
                if pause:
                    time.sleep(pause)
        return self._t("docking.sent")

    def control_cockpit_toggle(
        self, feature: str, requested_state: bool | None = None
    ) -> str:
        """Alterna vision nocturna o compuerta usando estado real y binding."""

        if not self.state.known:
            return self._t("cockpit.vehicle_unknown")
        srv_feature = feature in {
            "srv_lights", "srv_night_vision", "srv_cargo_scoop",
        }
        if srv_feature and not self.state.in_srv:
            return self._t("cockpit.not_srv")
        if not srv_feature and not self.state.in_main_ship:
            return self._t("cockpit.not_ship")
        if self.state.gui_focus != 0:
            return self._t("cockpit.panel_open")
        definitions = {
            "night_vision": (
                "NightVisionToggle", self.state.night_vision_on,
                self._t("cockpit.night_activated"), self._t("cockpit.night_deactivated"),
            ),
            "cargo_scoop": (
                "ToggleCargoScoop", self.state.cargo_scoop_deployed,
                self._t("cockpit.scoop_deployed"), self._t("cockpit.scoop_retracted"),
            ),
            "landing_gear": (
                "LandingGearToggle", self.state.landing_gear_down,
                self._t("cockpit.gear_deployed"), self._t("cockpit.gear_retracted"),
            ),
            "srv_lights": (
                "HeadlightsBuggyButton", self.state.lights_on,
                self._t("cockpit.srv_lights_on"), self._t("cockpit.srv_lights_off"),
            ),
            "srv_night_vision": (
                "NightVisionToggle", self.state.night_vision_on,
                self._t("cockpit.srv_night_on"), self._t("cockpit.srv_night_off"),
            ),
            "srv_cargo_scoop": (
                "ToggleCargoScoop_Buggy", self.state.cargo_scoop_deployed,
                self._t("cockpit.srv_scoop_deployed"),
                self._t("cockpit.srv_scoop_retracted"),
            ),
        }
        if feature == "hyperspace":
            if self.state.docked or self.state.landed:
                return self._t("cockpit.hyperspace_landed")
            return self._perform(
                "HyperSuperCombination",
                self._t("cockpit.hyperspace_started"),
            ) or (
                self._t("cockpit.hyperspace_failed")
            )
        definition = definitions.get(feature)
        if definition is None:
            return self._t("cockpit.unknown_control")
        action, current, enabled_text, disabled_text = definition
        target = (not current) if requested_state is None else requested_state
        if current == target:
            return enabled_text if target else disabled_text
        if self._binding(action) is None:
            return self._t("cockpit.binding_missing", feature=feature.replace("_", " "))
        result = enabled_text if target else disabled_text
        return self._perform(action, result) or (
            self._t("cockpit.control_failed")
        )

    def _set_gear(self, down: bool) -> str | None:
        if not self.state.known or not self.state.in_main_ship:
            return None
        if self.state.landing_gear_down == down:
            return None
        return self._perform(
            "LandingGearToggle",
            self._t("cockpit.gear_deployed" if down else "cockpit.gear_retracted"),
        )

    def _perform(self, action_name: str, result: str) -> str | None:
        now = time.monotonic()
        if self._last_action == action_name and now - self._last_action_at < 2.0:
            return None
        binding = self._binding(action_name)
        if binding is None or not self.sender.send(binding):
            return None
        self._last_action = action_name
        self._last_action_at = now
        return result

    def _binding(self, action_name: str) -> BindingInput | None:
        if self.audit is None:
            return None
        active = {name.casefold() for name in self.audit.active_presets}
        profiles = tuple(
            profile for profile in self.audit.profiles
            if profile.path.stem.split(".")[0].casefold() in active
            or profile.preset_name.casefold() in active
        )
        if not profiles:
            profiles = self.audit.profiles
        for profile in profiles:
            action: BindingAction | None = profile.actions.get(action_name)
            if action is None:
                continue
            for binding in (action.primary, action.secondary):
                if binding.configured and binding.device.casefold() == "keyboard":
                    return binding
        return None
