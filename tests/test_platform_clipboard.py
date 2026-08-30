import unittest
from unittest.mock import Mock, patch

from platform_adapters.clipboard import (
    ClipboardUnavailable,
    WindowsClipboardAdapter,
    copy_text,
    create_clipboard,
)


class ClipboardAdapterTests(unittest.TestCase):
    @patch("platform_adapters.clipboard.platform.system", return_value="Windows")
    def test_windows_selects_native_adapter(self, _system):
        self.assertIsInstance(create_clipboard(), WindowsClipboardAdapter)

    @patch("platform_adapters.clipboard.platform.system", return_value="Linux")
    def test_unsupported_platform_does_not_guess_or_simulate_keys(self, _system):
        with self.assertRaises(ClipboardUnavailable):
            create_clipboard()

    @patch("platform_adapters.clipboard.create_clipboard")
    def test_copy_text_delegates_to_selected_adapter(self, factory):
        adapter = Mock()
        factory.return_value = adapter
        copy_text("Sol")
        adapter.write_text.assert_called_once_with("Sol")


if __name__ == "__main__":
    unittest.main()
