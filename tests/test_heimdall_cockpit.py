from pathlib import Path
import unittest

from heimdall.bindings import BindingAction, BindingAudit, BindingInput, BindingProfile
from heimdall.cockpit import (
    CockpitAdvisor,
    CockpitState,
    DOCKED,
    IN_MAIN_SHIP,
    LANDED,
    LIGHTS_ON,
    NIGHT_VISION_ON,
    SUPERCRUISE,
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
    profile.actions["OrderRequestDock"] = BindingAction(
        "OrderRequestDock", BindingInput("Keyboard", "Key_O"), BindingInput("", "")
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

    def test_recognizes_docking_request_and_keeps_it_in_information_mode(self) -> None:
        advisor = CockpitAdvisor(audit())
        advisor.update_status({"Flags": IN_MAIN_SHIP})

        intent = parse_cockpit_intent("solicitá permiso de aterrizaje")
        answer = advisor.describe(intent)

        self.assertEqual(intent.feature, "docking_request")
        self.assertIn("Modo informativo", answer)
        self.assertIn("O", answer)
        self.assertIn("no enviaré ninguna pulsación", answer)

    def test_docking_request_is_blocked_in_incompatible_states(self) -> None:
        advisor = CockpitAdvisor(audit())
        intent = parse_cockpit_intent("pedí permiso para atracar")
        cases = (
            (IN_MAIN_SHIP | DOCKED, "ya está atracada"),
            (IN_MAIN_SHIP | LANDED, "en superficie"),
            (IN_MAIN_SHIP | SUPERCRUISE, "supercrucero"),
        )
        for flags, expected in cases:
            with self.subTest(flags=flags):
                advisor.update_status({"Flags": flags})
                self.assertIn(expected, advisor.describe(intent))


if __name__ == "__main__":
    unittest.main()
