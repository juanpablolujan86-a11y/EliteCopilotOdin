from pathlib import Path
import unittest

from heimdall.bindings import BindingAction, BindingAudit, BindingInput, BindingProfile
from heimdall.cockpit import (
    CockpitAdvisor,
    CockpitState,
    DOCKED,
    IN_MAIN_SHIP,
    IN_SRV,
    LANDED,
    LANDING_GEAR_DOWN,
    LIGHTS_ON,
    NIGHT_VISION_ON,
    SUPERCRUISE,
    parse_cockpit_intent,
)
from core.command_center import CommandCenter


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
    def test_recognizes_calibration_commands_in_english_and_portuguese(self) -> None:
        expected = {
            "request docking": "docking_request", "night vision": "night_vision",
            "cargo scoop": "cargo_scoop", "landing gear": "landing_gear",
            "hyperspace jump": "hyperspace", "solicitar atracação": "docking_request",
            "visão noturna": "night_vision", "coletor de carga": "cargo_scoop",
            "trem de pouso": "landing_gear", "salto no hiperespaço": "hyperspace",
        }
        for command, feature in expected.items():
            with self.subTest(command=command):
                intent = parse_cockpit_intent(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.feature, feature)

    def test_reads_cockpit_flags(self) -> None:
        state = CockpitState.from_status(
            {"Flags": IN_MAIN_SHIP | LIGHTS_ON | NIGHT_VISION_ON | LANDING_GEAR_DOWN}
        )
        self.assertTrue(state.in_main_ship)
        self.assertTrue(state.lights_on)
        self.assertTrue(state.night_vision_on)
        self.assertTrue(state.landing_gear_down)

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

    def test_recognizes_docking_request_as_contacts_panel_action(self) -> None:
        advisor = CockpitAdvisor(audit())
        advisor.update_status({"Flags": IN_MAIN_SHIP})

        intent = parse_cockpit_intent("solicitá permiso de aterrizaje")
        answer = advisor.describe(intent)

        self.assertEqual(intent.feature, "docking_request")
        self.assertIn("panel de Contactos", answer)

    def test_advisor_identifies_docking_as_contacts_panel_action(self) -> None:
        advisor = CockpitAdvisor(audit())
        intent = parse_cockpit_intent("pedí permiso para atracar")
        advisor.update_status({"Flags": IN_MAIN_SHIP})
        self.assertIn("panel de Contactos", advisor.describe(intent))

    def test_recognizes_short_cockpit_voice_commands(self) -> None:
        night = parse_cockpit_intent("ODIN luz nocturna")
        cargo = parse_cockpit_intent("ODIN, colector de carga")

        self.assertEqual((night.feature, night.requested_state), ("night_vision", None))
        self.assertEqual((cargo.feature, cargo.requested_state), ("cargo_scoop", None))

    def test_recognizes_gear_and_hyperspace_commands(self) -> None:
        gear = parse_cockpit_intent("ODIN, tren de aterrizaje")
        jump = parse_cockpit_intent("ODIN, hipersalto")
        self.assertEqual((gear.feature, gear.requested_state), ("landing_gear", None))
        self.assertEqual((jump.feature, jump.requested_state), ("hyperspace", True))
        self.assertEqual(
            parse_cockpit_intent("hiper salto").feature, "hyperspace"
        )
        self.assertEqual(
            parse_cockpit_intent("salto al hiperespacio").feature, "hyperspace"
        )
        self.assertTrue(CommandCenter._is_credible_voice_question("hipersalto"))
        self.assertEqual(
            parse_cockpit_intent("ODIN, baja el tren de aterrizaje").requested_state,
            True,
        )
        self.assertEqual(
            parse_cockpit_intent("ODIN, sube el tren de aterrizaje").requested_state,
            False,
        )

    def test_recognizes_srv_lights_and_night_vision(self) -> None:
        lights = parse_cockpit_intent("ODIN, encendé las luces del Scarab")
        night = parse_cockpit_intent("ODIN, visión nocturna del SRV")
        self.assertEqual((lights.feature, lights.requested_state), ("srv_lights", True))
        self.assertEqual(
            (night.feature, night.requested_state), ("srv_night_vision", None)
        )
        self.assertTrue(CockpitState.from_status({"Flags": IN_SRV}).in_srv)

    def test_accepts_vrs_transcription_for_scarab(self) -> None:
        intent = parse_cockpit_intent("ODIN, luces del VRS")
        self.assertEqual(intent.feature, "srv_lights")

    def test_recognizes_srv_cargo_scoop(self) -> None:
        intent = parse_cockpit_intent("ODIN, colector de carga del Scarab")
        self.assertEqual(
            (intent.feature, intent.requested_state), ("srv_cargo_scoop", None)
        )


if __name__ == "__main__":
    unittest.main()
