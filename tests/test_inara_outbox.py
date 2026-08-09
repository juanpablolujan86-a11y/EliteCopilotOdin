from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager
from services.inara_outbox import InaraOutbox


class InaraOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.db=DatabaseManager(self.root); self.db.connect(); self.db.create_tables()
        self.outbox=InaraOutbox(self.db)
        self.now=datetime(2026,8,9,12,0,tzinfo=timezone.utc)
        self.event={"eventName":"setCommanderCredits",
                    "eventTimestamp":"2026-08-09T12:00:00Z",
                    "eventData":{"commanderCredits":10}}

    def tearDown(self): self.db.disconnect(); self.temp.cleanup()

    def test_persists_translated_event_and_deduplicates(self):
        self.assertTrue(self.outbox.enqueue(self.event,now=self.now))
        self.assertFalse(self.outbox.enqueue(self.event,now=self.now))
        self.db.disconnect(); self.db.connect()
        self.assertEqual(InaraOutbox(self.db).due(now=self.now)[0].event,self.event)

    def test_rejects_incomplete_events(self):
        self.assertFalse(self.outbox.enqueue({"eventName":"x"},now=self.now))

    def test_failure_uses_exponential_retry(self):
        self.outbox.enqueue(self.event,now=self.now)
        batch=self.outbox.due(now=self.now)
        self.outbox.mark_failed(batch,"offline",now=self.now)
        self.assertEqual(self.outbox.due(now=self.now),())
        retried=self.outbox.due(now=self.now+timedelta(seconds=60))
        self.assertEqual(len(retried),1); self.assertEqual(retried[0].attempts,1)

    def test_marks_sent_and_rejected_transactionally(self):
        self.outbox.enqueue(self.event,now=self.now)
        self.outbox.mark_sent(self.outbox.due(now=self.now),now=self.now)
        second=dict(self.event,eventTimestamp="2026-08-09T12:01:00Z")
        self.outbox.enqueue(second,now=self.now)
        self.outbox.mark_rejected(self.outbox.due(now=self.now),"auth",now=self.now)
        self.assertEqual(self.outbox.counts(),{"rejected":1,"sent":1})


if __name__=="__main__": unittest.main()
