import unittest
from unittest.mock import patch

from platform_adapters.hotkey import (
    HotkeyUnavailable,
    VK_F7,
    VK_F8,
    create_hotkey,
)
from speech.hotkey import WindowsHotkey


class HotkeyAdapterTests(unittest.TestCase):
    @patch("platform_adapters.hotkey.platform.system", return_value="Windows")
    def test_windows_uses_native_hotkey_with_requested_key(self, _system):
        self.assertEqual(create_hotkey().virtual_key, VK_F8)
        self.assertEqual(create_hotkey(VK_F7).virtual_key, VK_F7)
        self.assertIsInstance(create_hotkey(), WindowsHotkey)

    @patch("platform_adapters.hotkey.platform.system", return_value="Darwin")
    def test_unsupported_platform_fails_explicitly(self, _system):
        with self.assertRaises(HotkeyUnavailable):
            create_hotkey()


if __name__ == "__main__":
    unittest.main()
