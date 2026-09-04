import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.command_center import CommandCenter


class PowerplayActivityFlowTests(unittest.TestCase):
    def setUp(self):
        self.center = CommandCenter.__new__(CommandCenter)
        self.center._powerplay_activity = {}
        self.center.commander_state = SimpleNamespace(
            powerplay_power="Li Yong-Rui",
            powerplay_merits=240159,
            star_position=(1.0, 2.0, 3.0),
        )

    @patch("core.command_center.threading.Thread")
    def test_trade_without_commodity_starts_automatic_search(self, thread):
        accepted, _detail = self.center.request_powerplay_activity("trade", "")

        self.assertTrue(accepted)
        self.assertEqual(self.center._powerplay_activity["subject"], "")
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_mining_still_requires_a_mineral(self):
        accepted, detail = self.center.request_powerplay_activity("mining", "")

        self.assertFalse(accepted)
        self.assertIn("mineral", detail.casefold())


if __name__ == "__main__":
    unittest.main()
