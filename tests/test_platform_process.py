import unittest
from unittest.mock import patch

from platform_adapters.process import hidden_process_flags


class ProcessAdapterTests(unittest.TestCase):
    @patch("platform_adapters.process.platform.system", return_value="Linux")
    def test_non_windows_never_receives_windows_creation_flags(self, _system):
        self.assertEqual(hidden_process_flags(detached=True, below_normal=True), 0)

    @patch("platform_adapters.process.platform.system", return_value="Windows")
    @patch("platform_adapters.process.subprocess.CREATE_NO_WINDOW", 1, create=True)
    @patch("platform_adapters.process.subprocess.DETACHED_PROCESS", 2, create=True)
    @patch("platform_adapters.process.subprocess.BELOW_NORMAL_PRIORITY_CLASS", 4, create=True)
    def test_windows_combines_only_requested_flags(self, _system):
        self.assertEqual(hidden_process_flags(), 1)
        self.assertEqual(hidden_process_flags(detached=True), 3)
        self.assertEqual(hidden_process_flags(below_normal=True), 5)
        self.assertEqual(hidden_process_flags(detached=True, below_normal=True), 7)


if __name__ == "__main__":
    unittest.main()
