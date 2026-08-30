import tempfile
import unittest
from pathlib import Path

from heimdall.bindings import BindingCustodian

PROFILE = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="Prueba" MajorVersion="4" MinorVersion="2">
  <KeyboardLayout>es-AR</KeyboardLayout>
  <ShipSpotLightToggle><Primary Device="Keyboard" Key="Key_L" /><Secondary Device="{NoDevice}" Key="" /></ShipSpotLightToggle>
  <NightVisionToggle><Primary Device="Keyboard" Key="Key_N"><Modifier Device="Keyboard" Key="Key_LeftShift" /></Primary><Secondary Device="{NoDevice}" Key="" /></NightVisionToggle>
  <ToggleCargoScoop><Primary Device="Keyboard" Key="Key_Home" /><Secondary Device="{NoDevice}" Key="" /></ToggleCargoScoop>
  <LandingGearToggle><Primary Device="Keyboard" Key="Key_L" /><Secondary Device="{NoDevice}" Key="" /></LandingGearToggle>
  <CycleNextPanel><Primary Device="Keyboard" Key="Key_E" /><Secondary Device="{NoDevice}" Key="" /></CycleNextPanel>
  <CyclePreviousPanel><Primary Device="Keyboard" Key="Key_Q" /><Secondary Device="{NoDevice}" Key="" /></CyclePreviousPanel>
  <UI_Back><Primary Device="Keyboard" Key="Key_Backspace" /><Secondary Device="{NoDevice}" Key="" /></UI_Back>
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
        self.assertEqual(profile.actions["CycleNextPanel"].primary.key, "Key_E")
        self.assertEqual(profile.actions["LandingGearToggle"].primary.key, "Key_L")
        self.assertEqual(profile.actions["ToggleCargoScoop"].primary.key, "Key_Home")

    def test_audit_creates_one_snapshot_per_configuration(self) -> None:
        first = self.custodian.audit()
        second = self.custodian.audit()
        self.assertEqual(first.active_presets[1], "Custom")
        self.assertIn("Missing devices: GamePad", first.loading_errors)
        self.assertEqual(first.snapshot_path, second.snapshot_path)
        self.assertTrue((first.snapshot_path / "manifest.json").exists())
        self.assertTrue((first.snapshot_path / "Custom.4.2.binds").exists())

    def test_restore_requires_literal_authorization_and_preserves_current_snapshot(self) -> None:
        original = self.custodian.audit().snapshot_path
        profile = self.bindings / "Custom.4.2.binds"
        profile.write_text(PROFILE.replace("Key_L", "Key_J", 1), encoding="utf-8")
        with self.assertRaises(PermissionError):
            self.custodian.restore_snapshot(original, confirmation="yes")

        result = self.custodian.restore_snapshot(
            original, confirmation="RESTORE_BINDINGS"
        )

        restored = self.custodian.parse_profile(profile)
        self.assertEqual(restored.actions["ShipSpotLightToggle"].primary.key, "Key_L")
        self.assertNotEqual(result.safety_snapshot, original)
        self.assertIn("Custom.4.2.binds", result.restored_files)

    def test_restore_rejects_snapshots_outside_the_safe_store(self) -> None:
        outside = self.data / "outside"
        outside.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "almacén seguro"):
            self.custodian.restore_snapshot(
                outside, confirmation="RESTORE_BINDINGS"
            )


if __name__ == "__main__":
    unittest.main()
