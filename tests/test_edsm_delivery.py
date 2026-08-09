from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

from core.database import DatabaseManager
from services.edsm_credentials import EDSMCredentials
from services.edsm_delivery import EDSMDeliveryService
from services.edsm_journal import EDSMSubmissionResult
from services.edsm_outbox import EDSMOutbox


class EDSMDeliveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.db=DatabaseManager(self.root); self.db.connect(); self.db.create_tables()
        self.outbox=EDSMOutbox(self.db)
        self.now=datetime(2026,8,9,12,0,tzinfo=timezone.utc)
        self.outbox.enqueue({"timestamp":"2026-08-09T12:00:00Z","event":"FSDJump"},
                            game_version="4.1",game_build="r1",now=self.now)

    def tearDown(self): self.db.disconnect(); self.temp.cleanup()

    def service(self,result,credentials=True):
        store=Mock(); store.get.return_value=(
            EDSMCredentials("CMDR Test","secret") if credentials else None
        )
        client=Mock(); client.submit.return_value=result
        return EDSMDeliveryService(
            self.root,credentials_factory=lambda:store,client_factory=lambda:client
        ),client

    def test_does_nothing_without_credentials(self):
        service,client=self.service(EDSMSubmissionResult(True,False,100,"OK"),False)
        self.assertEqual(service.process_once(now=self.now),0)
        client.submit.assert_not_called()

    def test_accepted_batch_is_completed(self):
        service,client=self.service(EDSMSubmissionResult(True,False,100,"OK"))
        with self.assertLogs("odin.edsm",level="INFO"):
            self.assertEqual(service.process_once(now=self.now),1)
        self.assertEqual(self.outbox.counts(),{"sent":1})

    def test_retryable_and_permanent_results_are_separated(self):
        service,_=self.service(EDSMSubmissionResult(False,True,429,"rate"))
        with self.assertLogs("odin.edsm",level="WARNING"):
            service.process_once(now=self.now)
        self.assertEqual(self.outbox.counts(),{"pending":1})


if __name__=="__main__": unittest.main()
