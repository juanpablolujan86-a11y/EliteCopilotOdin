from pathlib import Path
import unittest

from heimdall.bindings import BindingAction, BindingAudit, BindingInput, BindingProfile
from heimdall.cockpit import (
    CARGO_SCOOP_DEPLOYED,
    CockpitState,
    IN_MAIN_SHIP,
    IN_SRV,
    LANDING_GEAR_DOWN,
    NIGHT_VISION_ON,
)
from heimdall.docking_assist import DockingAssist


class FakeSender:
    def __init__(self) -> None:
        self.sent = []

    def send(self, binding: BindingInput) -> bool:
        self.sent.append(binding.key)
        return True


def audit() -> BindingAudit:
    profile = BindingProfile(Path("Custom.4.2.binds"), "Custom", "4", "2", "es-AR")
    profile.actions["LandingGearToggle"] = BindingAction(
        "LandingGearToggle", BindingInput("Keyboard", "Key_L"), BindingInput("", "")
    )
    keys = {
        "NightVisionToggle": "Key_I",
        "ToggleCargoScoop": "Key_Home",
        "HyperSuperCombination": "Key_J",
        "HeadlightsBuggyButton": "Key_L",
        "ToggleCargoScoop_Buggy": "Key_C",
        "FocusLeftPanel": "Key_1",
        "CyclePreviousPanel": "Key_Q",
        "CycleNextPanel": "Key_E",
        "UI_Select": "Key_Space",
        "UI_Right": "Key_D",
    }
    for action_name, key in keys.items():
        profile.actions[action_name] = BindingAction(
            action_name, BindingInput("Keyboard", key), BindingInput("", "")
        )
    return BindingAudit((profile,), ("Custom",), (), None)


class DockingAssistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sender = FakeSender()
        self.assist = DockingAssist(self.sender)
        self.assist.configure(enabled=True, audit=audit())

    def test_does_not_deploy_gear_when_docking_is_granted(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))
        result = self.assist.handle_journal({"event": "DockingGranted"})
        self.assertIsNone(result)
        self.assertEqual(self.sender.sent, [])

    def test_retracts_gear_on_takeoff(self) -> None:
        self.assist.update_status(
            CockpitState.from_status({"Flags": IN_MAIN_SHIP | LANDING_GEAR_DOWN})
        )
        result = self.assist.handle_journal({"event": "Liftoff"})
        self.assertEqual(result, "tren de aterrizaje replegado")
        self.assertEqual(self.sender.sent, ["Key_L"])

    def test_does_not_toggle_when_state_already_matches(self) -> None:
        self.assist.update_status(
            CockpitState.from_status({"Flags": IN_MAIN_SHIP | LANDING_GEAR_DOWN})
        )
        self.assertIsNone(self.assist.handle_journal({"event": "DockingGranted"}))
        self.assertEqual(self.sender.sent, [])

    def test_does_nothing_when_disabled(self) -> None:
        self.assist.configure(enabled=False, audit=audit())
        self.assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))
        self.assertIsNone(self.assist.handle_journal({"event": "DockingGranted"}))
        self.assertEqual(self.sender.sent, [])

    def test_requests_through_contacts_and_restores_navigation(self) -> None:
        self.assist.update_status(
            CockpitState.from_status({"Flags": IN_MAIN_SHIP, "GuiFocus": 0})
        )
        result = self.assist.request_station_docking()
        self.assertIn("Solicitud enviada", result)
        self.assertEqual(
            self.sender.sent,
            ["Key_1"] + ["Key_E"] * 2
            + ["Key_D", "Key_Space"]
            + ["Key_Q"] * 2 + ["Key_1"],
        )

    def test_refuses_request_when_an_interface_panel_is_open(self) -> None:
        self.assist.update_status(
            CockpitState.from_status({"Flags": IN_MAIN_SHIP, "GuiFocus": 2})
        )
        self.assertIn("panel abierto", self.assist.request_station_docking())
        self.assertEqual(self.sender.sent, [])

    def test_toggles_night_vision_from_real_status(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))
        result = self.assist.control_cockpit_toggle("night_vision")
        self.assertIn("vision nocturna activada", result)
        self.assertEqual(self.sender.sent, ["Key_I"])

    def test_retracts_cargo_scoop_when_deployed(self) -> None:
        self.assist.update_status(
            CockpitState.from_status({"Flags": IN_MAIN_SHIP | CARGO_SCOOP_DEPLOYED})
        )
        result = self.assist.control_cockpit_toggle("cargo_scoop", False)
        self.assertIn("colector de carga replegado", result)
        self.assertEqual(self.sender.sent, ["Key_Home"])

    def test_toggles_landing_gear_only_on_explicit_command(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))
        result = self.assist.control_cockpit_toggle("landing_gear")
        self.assertIn("tren de aterrizaje desplegado", result)
        self.assertEqual(self.sender.sent, ["Key_L"])

    def test_starts_hyperspace_from_explicit_command(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))
        result = self.assist.control_cockpit_toggle("hyperspace", True)
        self.assertIn("hipersalto", result)
        self.assertIn("motor de distorsión activado", result)
        self.assertEqual(self.sender.sent, ["Key_J"])

    def test_controls_srv_lights_only_inside_srv(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_SRV}))
        result = self.assist.control_cockpit_toggle("srv_lights", True)
        self.assertIn("luces del SRV encendidas", result)
        self.assertEqual(self.sender.sent, ["Key_L"])

    def test_blocks_srv_command_while_in_main_ship(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))
        result = self.assist.control_cockpit_toggle("srv_night_vision", True)
        self.assertIn("dentro del SRV", result)
        self.assertEqual(self.sender.sent, [])

    def test_controls_srv_cargo_scoop(self) -> None:
        self.assist.update_status(CockpitState.from_status({"Flags": IN_SRV}))
        result = self.assist.control_cockpit_toggle("srv_cargo_scoop", True)
        self.assertIn("colector de carga del SRV desplegado", result)
        self.assertEqual(self.sender.sent, ["Key_C"])

    def test_control_response_uses_selected_language(self) -> None:
        assist = DockingAssist(sender=self.sender, language="en-US")
        assist.configure(enabled=True, audit=audit())
        assist.update_status(CockpitState.from_status({"Flags": IN_MAIN_SHIP}))

        result = assist.control_cockpit_toggle("landing_gear", True)

        self.assertIn("landing gear deployed", result)


if __name__ == "__main__":
    unittest.main()
