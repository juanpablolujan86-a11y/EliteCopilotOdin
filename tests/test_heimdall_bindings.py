import tempfile
import unittest
from pathlib import Path

from heimdall.bindings import BindingCustodian

PROFILE = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="Prueba" MajorVersion="4" MinorVersion="2">
  <KeyboardLayout>es-AR</KeyboardLayout>
  <ShipSpotLightToggle><Primary Device="Keyboard" Key="Key_L" /><Secondary Device="{NoDevice}" Key="" /></ShipSpotLightToggle>
  <NightVisionToggle><Primary Device="Keyboard" Key="Key_N"><Modifier Device="Keyboard" Key="Key_LeftShift" /></Primary><Secondary Device="{NoDevice}" Key="" /></NightVisionToggle>
  <OrderRequestDock><Primary Device="{NoDevice}" Key="" /><Secondary Device="{NoDevice}" Key="" /></OrderRequestDock>
</Root>
"""


class BindingCustodianTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.bindings = root / "Bindings"
        self.data = root / "ODIN"
        self.bindings.mkdir()
        (self.bindings / "Custom.4.2.binds").write_text(PROFILE, encoding="utf-8")
        (self.bindings / "StartPreset.4.start").write_text(
            "GenericJoystick\nCustom\nCustom\nKeyboardMouseOnly\n", encoding="utf-8"
        )
        (self.bindings / "BindingLoadingErrors.log").write_text(
            "Missing devices: GamePad\n", encoding="utf-8"
        )
        self.custodian = BindingCustodian(self.bindings, self.data)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parses_actions_devices_and_modifiers(self) -> None:
        profile = self.custodian.parse_profile(self.bindings / "Custom.4.2.binds")
        self.assertEqual(profile.preset_name, "Prueba")
        self.assertEqual(profile.keyboard_layout, "es-AR")
        self.assertEqual(profile.actions["ShipSpotLightToggle"].primary.key, "Key_L")
        self.assertEqual(
            profile.actions["NightVisionToggle"].primary.modifiers,
            (("Keyboard", "Key_LeftShift"),),
        )
        self.assertFalse(profile.actions["OrderRequestDock"].configured)

    def test_audit_creates_one_snapshot_per_configuration(self) -> None:
        first = self.custodian.audit()
        second = self.custodian.audit()
        self.assertEqual(first.active_presets[1], "Custom")
        self.assertIn("Missing devices: GamePad", first.loading_errors)
        self.assertEqual(first.snapshot_path, second.snapshot_path)
        self.assertTrue((first.snapshot_path / "manifest.json").exists())
        self.assertTrue((first.snapshot_path / "Custom.4.2.binds").exists())


if __name__ == "__main__":
    unittest.main()
