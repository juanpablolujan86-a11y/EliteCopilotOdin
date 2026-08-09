import unittest

from core.config import Config


class HeimdallConfigTests(unittest.TestCase):
    def test_automatic_replan_is_opt_in(self) -> None:
        config = Config.__new__(Config)
        config.data = {}
        self.assertFalse(config.heimdall_auto_replan_enabled)

        config.data = {"heimdall_auto_replan_enabled": "sí"}
        self.assertTrue(config.heimdall_auto_replan_enabled)


if __name__ == "__main__":
    unittest.main()
