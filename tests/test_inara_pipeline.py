from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager
from services.inara_outbox import InaraOutbox
from services.inara_pipeline import InaraJournalPipeline


class InaraJournalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.db=DatabaseManager(self.root); self.db.connect(); self.db.create_tables()
        self.outbox=InaraOutbox(self.db); self.pipeline=InaraJournalPipeline(self.outbox)

    def tearDown(self): self.db.disconnect(); self.temp.cleanup()

    def test_maps_and_queues_supported_journal_event(self):
        self.assertEqual(self.pipeline.capture({
            "timestamp":"2026-08-09T12:00:00Z","event":"LoadGame","Credits":10
        }),1)
        self.assertEqual(self.outbox.counts(),{"pending":1})

    def test_ignores_unsupported_event(self):
        self.assertEqual(self.pipeline.capture({
            "timestamp":"2026-08-09T12:00:00Z","event":"Music"
        }),0)
        self.assertEqual(self.outbox.counts(),{})


if __name__=="__main__": unittest.main()
