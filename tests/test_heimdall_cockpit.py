from pathlib import Path
import unittest

from heimdall.bindings import BindingAction, BindingAudit, BindingInput, BindingProfile
from heimdall.cockpit import (
    CockpitAdvisor,
    CockpitState,
    IN_MAIN_SHIP,
    LIGHTS_ON,
    NIGHT_VISION_ON,
    parse_cockpit_intent,
)


def audit() -> BindingAudit:
    profile = BindingProfile(Path("Custom.4.2.binds"), "Custom", "4", "2", "es-AR")
    profile.actions["ShipSpotLightToggle"] = BindingAction(
        "ShipSpotLightToggle", BindingInput("Keyboard", "Key_L"), BindingInput("", "")
    )
    profile.actions["NightVisionToggle"] = BindingAction(
        "NightVisionToggle",
        BindingInput("Keyboard", "Key_N", (("Keyboard", "Key_LeftShift"),)),
        BindingInput("", ""),
    )
    return BindingAudit((profile,), ("Custom",), (), None)


class CockpitAdvisorTests(unittest.TestCase):
    def test_reads_cockpit_flags(self) -> None:
        state = CockpitState.from_status(
            {"Flags": IN_MAIN_SHIP | LIGHTS_ON | NIGHT_VISION_ON}
        )
        self.assertTrue(state.in_main_ship)
        self.assertTrue(state.lights_on)
        self.assertTrue(state.night_vision_on)

    def test_reports_existing_state_without_simulating_key(self) -> None:
        advisor = CockpitAdvisor(audit())
        advisor.update_status({"Flags": IN_MAIN_SHIP | LIGHTS_ON})
        answer = advisor.describe(parse_cockpit_intent("apagá las luces"))
        self.assertIn("Modo informativo", answer)
        self.assertIn("L", answer)
        self.assertIn("no enviaré ninguna pulsación", answer)

    def test_avoids_toggle_when_requested_state_already_matches(self) -> None:
        advisor = CockpitAdvisor(audit())
        advisor.update_status({"Flags": IN_MAIN_SHIP | NIGHT_VISION_ON})
        answer = advisor.describe(parse_cockpit_intent("activá la visión nocturna"))
        self.assertIn("ya está activada", answer)

    def test_blocks_action_outside_main_ship(self) -> None:
        advisor = CockpitAdvisor(audit())
        advisor.update_status({"Flags": 0})
        answer = advisor.describe(parse_cockpit_intent("prendé las luces"))
        self.assertIn("No confirmo", answer)


if __name__ == "__main__":
    unittest.main()
