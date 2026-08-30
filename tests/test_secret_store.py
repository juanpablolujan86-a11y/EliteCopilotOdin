import unittest
from unittest.mock import patch

from security.secret_store import SecretStoreUnavailable, create_secret_store
from voice.credentials import WindowsCredentialStore


class SecretStoreTests(unittest.TestCase):
    @patch("security.secret_store.platform.system", return_value="Windows")
    def test_windows_uses_credential_manager(self, _system):
        store = create_secret_store("ODIN/Test")
        self.assertIsInstance(store, WindowsCredentialStore)
        self.assertEqual(store.target, "ODIN/Test")

    @patch("security.secret_store.platform.system", return_value="Linux")
    def test_unsupported_platform_never_falls_back_to_plain_text(self, _system):
        with self.assertRaisesRegex(SecretStoreUnavailable, "almacén seguro"):
            create_secret_store("ODIN/Test")


if __name__ == "__main__":
    unittest.main()
