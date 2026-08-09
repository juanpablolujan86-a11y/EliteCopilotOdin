from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

from core.database import DatabaseManager
from services.eddn_pipeline import EDDNJournalPipeline


class EDDNJournalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.database=DatabaseManager(self.root)
        self.database.connect()
        self.database.create_tables()

    def tearDown(self):
        self.database.disconnect()
        self.temp.cleanup()

    def test_pipeline_captures_only_valid_supported_events(self):
        pipeline=EDDNJournalPipeline.create(self.root,self.database,"0.9.0")
        pipeline.capture({"event":"Fileheader","gameversion":"4.1.3.0"})
        self.assertFalse(pipeline.capture({"event":"Music"}))
        self.assertTrue(pipeline.capture({
            "timestamp":"2026-08-09T12:00:00Z","event":"Location",
            "StarSystem":"Sol","StarPos":[0,0,0],"SystemAddress":1,
        }))
        self.assertTrue(pipeline.capture({
            "timestamp":"2026-08-09T12:01:00Z","event":"Scan","BodyID":1,
        }))
        self.assertEqual(pipeline.outbox.pending_count(),2)

    def test_anonymous_identity_is_stable_and_contains_no_commander_data(self):
        first=EDDNJournalPipeline.create(self.root,self.database,"0.9.0")
        second=EDDNJournalPipeline.create(self.root,self.database,"0.9.0")

        self.assertEqual(first.builder.uploader_id,second.builder.uploader_id)
        self.assertTrue(first.builder.uploader_id.startswith("odin-"))
        self.assertNotIn("commander",first.builder.uploader_id.casefold())

    def test_duplicate_event_is_queued_only_once(self):
        pipeline=EDDNJournalPipeline.create(self.root,self.database,"0.9.0")
        event={
            "timestamp":"2026-08-09T12:00:00Z","event":"FSDJump",
            "StarSystem":"Sol","StarPos":[0,0,0],"SystemAddress":1,
        }
        self.assertTrue(pipeline.capture(event))
        self.assertFalse(pipeline.capture(event))
        self.assertEqual(pipeline.outbox.pending_count(),1)

    def test_bootstrap_restores_metadata_and_location_without_queueing_history(self):
        journal=self.root/"Journal.test.log"
        journal.write_text(
            '\n'.join((
                '{"event":"Fileheader","gameversion":"4.1","build":"r1"}',
                '{"event":"LoadGame","Horizons":true,"Odyssey":true}',
                '{"timestamp":"2026-08-09T12:00:00Z","event":"Location",'
                '"StarSystem":"Sol","StarPos":[0,0,0],"SystemAddress":1}',
                '{"timestamp":"2026-08-09T12:01:00Z","event":"Scan","BodyID":1}',
            )),encoding="utf-8"
        )
        pipeline=EDDNJournalPipeline.create(self.root,self.database,"0.9.0")

        pipeline.bootstrap_journal(journal)

        self.assertEqual(pipeline.outbox.pending_count(),0)
        self.assertTrue(pipeline.capture({
            "timestamp":"2026-08-09T12:02:00Z","event":"Scan","BodyID":2,
        }))
        envelope=pipeline.outbox.due()[0].envelope
        self.assertEqual(envelope["header"]["gameversion"],"4.1")
        self.assertEqual(envelope["message"]["StarSystem"],"Sol")
        self.assertTrue(envelope["message"]["odyssey"])

    def test_queue_failure_does_not_escape_into_main_journal_loop(self):
        pipeline=EDDNJournalPipeline.create(self.root,self.database,"0.9.0")
        pipeline.outbox.enqueue=Mock(side_effect=OSError("disco ocupado"))
        with self.assertLogs("odin.eddn",level="ERROR"):
            self.assertFalse(pipeline.capture({
                "timestamp":"2026-08-09T12:00:00Z","event":"Location",
                "StarSystem":"Sol","StarPos":[0,0,0],"SystemAddress":1,
            }))


if __name__=="__main__":
    unittest.main()
