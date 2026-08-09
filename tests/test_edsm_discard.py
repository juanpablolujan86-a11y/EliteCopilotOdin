import json
from pathlib import Path
import tempfile
from unittest.mock import Mock
import unittest

import requests

from services.edsm_discard import EDSMDiscardRegistry


class EDSMDiscardRegistryTests(unittest.TestCase):
    def test_refresh_persists_and_exposes_valid_list(self):
        with tempfile.TemporaryDirectory() as directory:
            session=Mock(); response=Mock()
            response.json.return_value=["Music","Fileheader"]
            session.get.return_value=response
            registry=EDSMDiscardRegistry(Path(directory),session=session)
            self.assertTrue(registry.refresh())
            self.assertIn("Music",registry)
            cached=json.loads((Path(directory)/"edsm_discard_events.json").read_text())
            self.assertEqual(cached,["Fileheader","Music"])

    def test_failed_refresh_preserves_cached_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"edsm_discard_events.json"
            path.write_text('["Music"]',encoding="utf-8")
            session=Mock(); session.get.side_effect=requests.ConnectionError("offline")
            registry=EDSMDiscardRegistry(Path(directory),session=session)
            with self.assertLogs("odin.edsm",level="WARNING"):
                self.assertFalse(registry.refresh())
            self.assertIn("Music",registry)

    def test_invalid_or_empty_remote_list_does_not_replace_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"edsm_discard_events.json"
            path.write_text('["Music"]',encoding="utf-8")
            session=Mock(); response=Mock(); response.json.return_value=[]
            session.get.return_value=response
            registry=EDSMDiscardRegistry(Path(directory),session=session)
            with self.assertLogs("odin.edsm",level="WARNING"):
                self.assertFalse(registry.refresh())
            self.assertEqual(registry.snapshot(),frozenset({"Music"}))


if __name__=="__main__": unittest.main()
