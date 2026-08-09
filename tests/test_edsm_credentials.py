from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

from services.edsm_credentials import EDSMCredentialStore
from services.edsm_key_file import import_edsm_key_file


class EDSMCredentialTests(unittest.TestCase):
    def test_round_trip_uses_protected_store(self):
        protected=Mock(); protected.get.return_value=None
        credentials=EDSMCredentialStore(protected)
        credentials.set("CMDR Test","secret-key")
        serialized=protected.set.call_args.args[0]
        protected.get.return_value=serialized
        restored=credentials.get()
        self.assertEqual(restored.commander_name,"CMDR Test")
        self.assertEqual(restored.api_key,"secret-key")

    def test_invalid_protected_payload_is_ignored(self):
        protected=Mock(); protected.get.return_value="not-json"
        self.assertIsNone(EDSMCredentialStore(protected).get())

    def test_import_cleans_plain_text_after_protecting_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"EDSM_API_KEY.txt"
            path.write_text("COMMANDER=CMDR Test\nAPI_KEY=secret-key\n",encoding="utf-8")
            credentials=Mock()
            result=import_edsm_key_file(root,credentials)
            self.assertTrue(result.imported)
            credentials.set.assert_called_once_with("CMDR Test","secret-key")
            cleaned=path.read_text(encoding="utf-8")
            self.assertNotIn("secret-key",cleaned)
            self.assertIn("PEGAR_API_KEY_AQUI",cleaned)

    def test_incomplete_file_is_not_imported_or_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"EDSM_API_KEY.txt"
            original="COMMANDER=CMDR Test\nAPI_KEY=PEGAR_API_KEY_AQUI\n"
            path.write_text(original,encoding="utf-8")
            credentials=Mock()
            result=import_edsm_key_file(root,credentials)
            self.assertFalse(result.imported)
            credentials.set.assert_not_called()
            self.assertEqual(path.read_text(encoding="utf-8"),original)

    def test_import_accepts_api_key_pasted_on_its_own_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"EDSM_API_KEY.txt"
            path.write_text("COMMANDER=CMDR Test\nsecret-key\n",encoding="utf-8")
            credentials=Mock()
            result=import_edsm_key_file(root,credentials)
            self.assertTrue(result.imported)
            credentials.set.assert_called_once_with("CMDR Test","secret-key")
            self.assertNotIn("secret-key",path.read_text(encoding="utf-8"))

    def test_plain_file_is_ignored_by_git(self):
        ignore=(Path(__file__).parents[1]/".gitignore").read_text(encoding="utf-8")
        self.assertIn("EDSM_API_KEY.txt",ignore)


if __name__=="__main__": unittest.main()
