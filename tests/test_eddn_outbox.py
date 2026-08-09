from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager
from services.eddn_outbox import EDDNOutbox


class EDDNOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.database=DatabaseManager(self.root)
        self.database.connect()
        self.database.create_tables()
        self.outbox=EDDNOutbox(self.database)
        self.now=datetime(2026,8,9,12,0,tzinfo=timezone.utc)
        self.envelope={
            "$schemaRef":"https://eddn.edcd.io/schemas/journal/1",
            "header":{"uploaderID":"anonymous","softwareName":"ODIN",
                      "softwareVersion":"0.9.0"},
            "message":{"timestamp":"2026-08-09T12:00:00Z","event":"FSDJump",
                       "StarSystem":"Sol","StarPos":[0,0,0],
                       "SystemAddress":10477373803},
        }

    def tearDown(self):
        self.database.disconnect()
        self.temp.cleanup()

    def test_persists_and_deduplicates_identical_envelope(self):
        self.assertTrue(self.outbox.enqueue(self.envelope,now=self.now))
        self.assertFalse(self.outbox.enqueue(self.envelope,now=self.now))
        self.database.disconnect()
        self.database.connect()

        restored=EDDNOutbox(self.database)

        self.assertEqual(restored.pending_count(),1)
        self.assertEqual(restored.due(now=self.now)[0].event_type,"FSDJump")

    def test_failure_uses_exponential_retry_without_losing_message(self):
        self.outbox.enqueue(self.envelope,now=self.now)
        item=self.outbox.due(now=self.now)[0]

        self.outbox.mark_failed(item.message_key,"sin red",now=self.now)

        self.assertEqual(self.outbox.due(now=self.now),())
        retry=self.outbox.due(now=self.now+timedelta(seconds=15))[0]
        self.assertEqual(retry.attempts,1)
        self.outbox.mark_failed(retry.message_key,"sin red",now=self.now+timedelta(seconds=15))
        self.assertEqual(
            self.outbox.due(now=self.now+timedelta(seconds=44)),()
        )
        self.assertEqual(
            self.outbox.due(now=self.now+timedelta(seconds=45))[0].attempts,2
        )

    def test_sent_message_leaves_pending_queue(self):
        self.outbox.enqueue(self.envelope,now=self.now)
        item=self.outbox.due(now=self.now)[0]

        self.outbox.mark_sent(item.message_key,now=self.now)

        self.assertEqual(self.outbox.pending_count(),0)
        self.assertEqual(self.outbox.due(now=self.now+timedelta(days=1)),())

    def test_future_message_is_not_due_early_and_limit_is_bounded(self):
        future=self.now+timedelta(minutes=1)
        self.outbox.enqueue(self.envelope,now=future)
        self.assertEqual(self.outbox.due(limit=0,now=self.now),())
        self.assertEqual(len(self.outbox.due(limit=0,now=future)),1)


if __name__=="__main__":
    unittest.main()
