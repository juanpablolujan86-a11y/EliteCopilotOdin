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
        retry=self.outbox.due(now=self.now+timedelta(seconds=60))[0]
        self.assertEqual(retry.attempts,1)
        self.outbox.mark_failed(retry.message_key,"sin red",now=self.now+timedelta(seconds=60))
        self.assertEqual(
            self.outbox.due(now=self.now+timedelta(seconds=179)),()
        )
        self.assertEqual(
            self.outbox.due(now=self.now+timedelta(seconds=180))[0].attempts,2
        )

    def test_rejected_message_is_never_retried(self):
        self.outbox.enqueue(self.envelope,now=self.now)
        item=self.outbox.due(now=self.now)[0]
        self.outbox.mark_rejected(item.message_key,"HTTP 400",now=self.now)
        self.assertEqual(self.outbox.pending_count(),0)
        self.assertEqual(self.outbox.due(now=self.now+timedelta(days=30)),())

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

    def test_summary_reports_counts_retries_and_last_event_type(self):
        self.outbox.enqueue(self.envelope,now=self.now)
        item=self.outbox.due(now=self.now)[0]
        self.outbox.mark_failed(item.message_key,"sin red",now=self.now)
        second=dict(self.envelope)
        second["message"]=dict(self.envelope["message"],timestamp="2026-08-09T12:01:00Z")
        self.outbox.enqueue(second,now=self.now)
        sent=self.outbox.due(now=self.now)[0]
        self.outbox.mark_sent(sent.message_key,now=self.now)

        summary=self.outbox.summary()

        self.assertEqual((summary.pending,summary.sent,summary.rejected),(1,1,0))
        self.assertEqual(summary.retrying,1)
        self.assertEqual(summary.last_sent_event,"FSDJump")

    def test_cleanup_removes_only_old_completed_messages(self):
        old=self.now-timedelta(days=100)
        self.outbox.enqueue(self.envelope,now=old)
        old_item=self.outbox.due(now=old)[0]
        self.outbox.mark_sent(old_item.message_key,now=old)

        rejected=dict(self.envelope)
        rejected["message"]=dict(
            self.envelope["message"],timestamp="2026-05-01T12:00:00Z"
        )
        self.outbox.enqueue(rejected,now=old)
        rejected_item=self.outbox.due(now=old)[0]
        self.outbox.mark_rejected(rejected_item.message_key,"bad",now=old)

        pending=dict(self.envelope)
        pending["message"]=dict(
            self.envelope["message"],timestamp="2026-04-01T12:00:00Z"
        )
        self.outbox.enqueue(pending,now=old)

        recent=dict(self.envelope)
        recent["message"]=dict(
            self.envelope["message"],timestamp="2026-08-08T12:00:00Z"
        )
        self.outbox.enqueue(recent,now=self.now-timedelta(days=1))
        recent_item=[item for item in self.outbox.due(now=self.now)
                     if item.envelope["message"]["timestamp"].startswith("2026-08")][0]
        self.outbox.mark_sent(recent_item.message_key,now=self.now-timedelta(days=1))

        removed=self.outbox.purge_completed(now=self.now)

        self.assertEqual(removed,2)
        summary=self.outbox.summary()
        self.assertEqual((summary.pending,summary.sent,summary.rejected),(1,1,0))

    def test_cleanup_retention_has_minimum_one_day(self):
        recent=self.now-timedelta(hours=12)
        self.outbox.enqueue(self.envelope,now=recent)
        item=self.outbox.due(now=recent)[0]
        self.outbox.mark_sent(item.message_key,now=recent)
        self.assertEqual(
            self.outbox.purge_completed(sent_days=0,rejected_days=0,now=self.now),0
        )


if __name__=="__main__":
    unittest.main()
