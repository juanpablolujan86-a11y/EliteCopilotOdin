from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager
from services.edsm_outbox import EDSMOutbox


class EDSMOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.db=DatabaseManager(self.root); self.db.connect(); self.db.create_tables()
        self.outbox=EDSMOutbox(self.db)
        self.now=datetime(2026,8,9,12,0,tzinfo=timezone.utc)
        self.event={"timestamp":"2026-08-09T12:00:00Z","event":"FSDJump",
                    "StarSystem":"Sol","FuelLevel":12.5}

    def tearDown(self): self.db.disconnect(); self.temp.cleanup()

    def enqueue(self,event=None,now=None):
        return self.outbox.enqueue(
            event or self.event,game_version="4.1",game_build="r1",
            now=now or self.now,
        )

    def test_persists_unmodified_event_and_deduplicates(self):
        self.assertTrue(self.enqueue())
        self.assertFalse(self.enqueue())
        self.db.disconnect(); self.db.connect()
        restored=EDSMOutbox(self.db).due(now=self.now)[0]
        self.assertEqual(restored.event,self.event)
        self.assertEqual(restored.event["FuelLevel"],12.5)

    def test_rejects_incomplete_or_legacy_events(self):
        self.assertFalse(self.outbox.enqueue(
            {"event":"Music"},game_version="4.1",game_build="r1",now=self.now
        ))
        self.assertFalse(self.outbox.enqueue(
            self.event,game_version="3.8.0",game_build="r1",now=self.now
        ))

    def test_batch_failure_retries_all_items_after_one_minute(self):
        self.enqueue()
        second=dict(self.event,timestamp="2026-08-09T12:01:00Z")
        self.enqueue(second)
        items=self.outbox.due(now=self.now)
        self.outbox.mark_failed(items,"sin red",now=self.now)
        self.assertEqual(self.outbox.due(now=self.now),())
        retried=self.outbox.due(now=self.now+timedelta(seconds=60))
        self.assertEqual(len(retried),2)
        self.assertTrue(all(item.attempts==1 for item in retried))

    def test_marks_batch_sent_or_rejected_transactionally(self):
        self.enqueue(); items=self.outbox.due(now=self.now)
        self.outbox.mark_sent(items,now=self.now)
        self.assertEqual(self.outbox.counts(),{"sent":1})
        second=dict(self.event,timestamp="2026-08-09T12:01:00Z")
        self.enqueue(second); items=self.outbox.due(now=self.now)
        self.outbox.mark_rejected(items,"credenciales",now=self.now)
        self.assertEqual(self.outbox.counts(),{"rejected":1,"sent":1})

    def test_due_batch_is_capped_at_official_client_limit(self):
        for index in range(105):
            self.enqueue(dict(self.event,timestamp=f"2026-08-09T12:{index:02d}:00Z"))
        self.assertEqual(len(self.outbox.due(limit=1000,now=self.now)),100)


if __name__=="__main__": unittest.main()
