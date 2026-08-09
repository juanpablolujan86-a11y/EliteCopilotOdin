from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager
from services.edsm_outbox import EDSMOutbox
from services.edsm_pipeline import EDSMJournalPipeline


class EDSMJournalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.db=DatabaseManager(self.root); self.db.connect(); self.db.create_tables()
        self.pipeline=EDSMJournalPipeline(EDSMOutbox(self.db))

    def tearDown(self): self.db.disconnect(); self.temp.cleanup()

    def test_bootstrap_restores_version_without_queueing_history(self):
        journal=self.root/"Journal.log"
        journal.write_text(
            '{"event":"Fileheader","gameversion":"4.1","build":"r1"}\n'
            '{"timestamp":"2026-08-09T12:00:00Z","event":"FSDJump"}\n',
            encoding="utf-8",
        )
        self.pipeline.bootstrap_journal(journal)
        self.assertEqual(self.pipeline.outbox.counts(),{})
        self.assertTrue(self.pipeline.capture({
            "timestamp":"2026-08-09T12:01:00Z","event":"FSDJump"
        }))

    def test_fileheader_updates_metadata_but_is_not_queued(self):
        self.assertFalse(self.pipeline.capture({
            "event":"Fileheader","gameversion":"4.1","build":"r1"
        }))
        self.assertEqual(self.pipeline.outbox.counts(),{})

    def test_event_is_not_captured_before_metadata_exists(self):
        self.assertFalse(self.pipeline.capture({
            "timestamp":"2026-08-09T12:00:00Z","event":"FSDJump"
        }))


if __name__=="__main__": unittest.main()
