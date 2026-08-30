import unittest
from unittest.mock import patch

from core.single_instance import SingleInstance
from platform_adapters.single_instance import (
    SingleInstanceUnavailable,
    create_single_instance,
)


class SingleInstanceAdapterTests(unittest.TestCase):
    @patch("platform_adapters.single_instance.platform.system", return_value="Windows")
    def test_windows_uses_native_named_mutex(self, _system):
        instance = create_single_instance("Local\\ODIN-Test-Adapter")
        self.assertIsInstance(instance, SingleInstance)
        self.assertEqual(instance.name, "Local\\ODIN-Test-Adapter")

    @patch("platform_adapters.single_instance.platform.system", return_value="Linux")
    def test_unsupported_platform_fails_instead_of_allowing_duplicates(self, _system):
        with self.assertRaises(SingleInstanceUnavailable):
            create_single_instance()


if __name__ == "__main__":
    unittest.main()
