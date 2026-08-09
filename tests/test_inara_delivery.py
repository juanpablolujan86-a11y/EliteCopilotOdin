from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

from core.database import DatabaseManager
from services.inara_client import InaraSubmissionResult
from services.inara_credentials import InaraCredentials
from services.inara_delivery import InaraDeliveryService
from services.inara_outbox import InaraOutbox


class InaraDeliveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.db=DatabaseManager(self.root); self.db.connect(); self.db.create_tables()
        self.outbox=InaraOutbox(self.db)
        self.now=datetime(2026,8,9,12,0,tzinfo=timezone.utc)
        self.outbox.enqueue({"eventName":"setCommanderCredits",
                             "eventTimestamp":"2026-08-09T12:00:00Z",
                             "eventData":{"commanderCredits":10}},now=self.now)

    def tearDown(self): self.db.disconnect(); self.temp.cleanup()

    def service(self,result,credentials=True):
        store=Mock(); store.get.return_value=(
            InaraCredentials("CMDR Test","F123","secret") if credentials else None
        )
        client=Mock(); client.submit.return_value=result
        return InaraDeliveryService(
            self.root,credentials_factory=lambda:store,client_factory=lambda:client
        ),client

    def test_does_nothing_without_credentials(self):
        service,client=self.service(InaraSubmissionResult(True,False,200,"OK"),False)
        self.assertEqual(service.process_once(now=self.now),0)
        client.submit.assert_not_called()

    def test_accepted_batch_is_completed_in_development_mode(self):
        service,client=self.service(InaraSubmissionResult(True,False,200,"OK"))
        with self.assertLogs("odin.inara",level="INFO"):
            self.assertEqual(service.process_once(now=self.now),1)
        self.assertEqual(self.outbox.counts(),{"sent":1})
        self.assertTrue(client.submit.call_args.kwargs["is_being_developed"])

    def test_retryable_result_preserves_event(self):
        service,_=self.service(InaraSubmissionResult(False,True,429,"rate"))
        with self.assertLogs("odin.inara",level="WARNING"):
            service.process_once(now=self.now)
        self.assertEqual(self.outbox.counts(),{"pending":1})


if __name__=="__main__": unittest.main()
