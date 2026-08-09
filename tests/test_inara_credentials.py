from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

from services.inara_credentials import InaraCredentialStore
from services.inara_key_file import import_inara_key_file


class InaraCredentialTests(unittest.TestCase):
    def test_round_trip_includes_optional_frontier_id(self):
        protected=Mock(); protected.get.return_value=None
        credentials=InaraCredentialStore(protected)
        credentials.set("CMDR Test","secret-key","F123456")
        serialized=protected.set.call_args.args[0]
        protected.get.return_value=serialized
        restored=credentials.get()
        self.assertEqual(restored.commander_name,"CMDR Test")
        self.assertEqual(restored.frontier_id,"F123456")
        self.assertEqual(restored.api_key,"secret-key")

    def test_invalid_payload_is_ignored(self):
        protected=Mock(); protected.get.return_value="[]"
        self.assertIsNone(InaraCredentialStore(protected).get())

    def test_import_protects_and_cleans_plain_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"INARA_API_KEY.txt"
            path.write_text(
                "COMMANDER=CMDR Test\nFRONTIER_ID=F123456\nAPI_KEY=secret-key\n",
                encoding="utf-8",
            )
            credentials=Mock()
            result=import_inara_key_file(root,credentials)
            self.assertTrue(result.imported)
            credentials.set.assert_called_once_with("CMDR Test","secret-key","F123456")
            cleaned=path.read_text(encoding="utf-8")
            self.assertNotIn("secret-key",cleaned)
            self.assertIn("PEGAR_API_KEY_AQUI",cleaned)

    def test_placeholder_is_not_imported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"INARA_API_KEY.txt"
            path.write_text(
                "COMMANDER=CMDR Test\nAPI_KEY=PEGAR_API_KEY_AQUI\n",
                encoding="utf-8",
            )
            credentials=Mock()
            self.assertFalse(import_inara_key_file(root,credentials).imported)
            credentials.set.assert_not_called()

    def test_import_accepts_api_key_pasted_on_its_own_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"INARA_API_KEY.txt"
            path.write_text(
                "COMMANDER=CMDR Test\nFRONTIER_ID=F123456\nsecret-key\n",
                encoding="utf-8",
            )
            credentials=Mock()
            result=import_inara_key_file(root,credentials)
            self.assertTrue(result.imported)
            credentials.set.assert_called_once_with("CMDR Test","secret-key","F123456")
            self.assertNotIn("secret-key",path.read_text(encoding="utf-8"))

    def test_import_discovers_missing_identity_from_latest_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"INARA_API_KEY.txt"
            path.write_text(
                "COMMANDER=\nFRONTIER_ID=\nsecret-key\n",encoding="utf-8"
            )
            journals=root/"journals"; journals.mkdir()
            (journals/"Journal.01.log").write_text(
                '{"timestamp":"2026-08-09T12:00:00Z","event":"LoadGame",'
                '"Commander":"CMDR Journal","FID":"F987654"}\n',
                encoding="utf-8",
            )
            credentials=Mock()
            result=import_inara_key_file(
                root,credentials,journal_path=journals
            )
            self.assertTrue(result.imported)
            credentials.set.assert_called_once_with(
                "CMDR Journal","secret-key","F987654"
            )

    def test_explicit_identity_takes_priority_over_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/"INARA_API_KEY.txt"
            path.write_text(
                "COMMANDER=CMDR Explicit\nFRONTIER_ID=F111\nsecret-key\n",
                encoding="utf-8",
            )
            journals=root/"journals"; journals.mkdir()
            (journals/"Journal.01.log").write_text(
                '{"event":"LoadGame","Commander":"CMDR Journal","FID":"F999"}\n',
                encoding="utf-8",
            )
            credentials=Mock()
            import_inara_key_file(root,credentials,journal_path=journals)
            credentials.set.assert_called_once_with(
                "CMDR Explicit","secret-key","F111"
            )


if __name__=="__main__": unittest.main()
