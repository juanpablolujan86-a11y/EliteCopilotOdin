import unittest
from unittest.mock import patch

from heimdall.docking_assist import WindowsEliteKeySender
from platform_adapters.cockpit import (
    CockpitControlUnavailable,
    create_cockpit_sender,
)


class CockpitAdapterTests(unittest.TestCase):
    @patch("platform_adapters.cockpit.platform.system", return_value="Windows")
    def test_windows_selects_guarded_elite_sender(self, _system):
        self.assertIsInstance(create_cockpit_sender(), WindowsEliteKeySender)

    @patch("platform_adapters.cockpit.platform.system", return_value="Linux")
    def test_unsupported_platform_never_sends_guessed_keys(self, _system):
        with self.assertRaises(CockpitControlUnavailable):
            create_cockpit_sender()


if __name__ == "__main__":
    unittest.main()
