from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

import requests

from core.database import DatabaseManager
from services.eddn_outbox import EDDNOutbox
from services.eddn_transport import EDDNDeliveryWorker, EDDNHTTPClient


class EDDNTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=DatabaseManager(Path(self.temp.name)); self.db.connect(); self.db.create_tables()
        self.outbox=EDDNOutbox(self.db)
        self.now=datetime(2026,8,9,12,0,tzinfo=timezone.utc)
        self.envelope={"$schemaRef":"schema","header":{},"message":{"event":"Scan"}}

    def tearDown(self):
        self.db.disconnect(); self.temp.cleanup()

    def response(self,status,text):
        result=Mock(); result.status_code=status; result.text=text; return result

    def test_posts_utf8_json_to_exact_official_endpoint(self):
        session=Mock(); session.post.return_value=self.response(200,"OK")
        result=EDDNHTTPClient(session).send(self.envelope)
        self.assertTrue(result.accepted)
        call=session.post.call_args
        self.assertEqual(call.args[0],"https://eddn.edcd.io:4430/upload/")
        self.assertEqual(call.kwargs["headers"]["Content-Type"],"application/json; charset=utf-8")
        self.assertEqual(call.kwargs["timeout"],(5,15))

    def test_http_400_and_426_are_permanent_failures(self):
        for status in (400,426):
            session=Mock(); session.post.return_value=self.response(status,"FAIL")
            result=EDDNHTTPClient(session).send(self.envelope)
            self.assertFalse(result.accepted); self.assertFalse(result.retryable)

    def test_network_and_service_failures_are_retryable(self):
        session=Mock(); session.post.side_effect=requests.ConnectionError("sin red")
        self.assertTrue(EDDNHTTPClient(session).send(self.envelope).retryable)
        session=Mock(); session.post.return_value=self.response(503,"FAIL")
        self.assertTrue(EDDNHTTPClient(session).send(self.envelope).retryable)

    def test_worker_rejects_bad_message_and_continues_with_next(self):
        first=self.envelope | {"message":{"event":"Scan","id":1}}
        second=self.envelope | {"message":{"event":"Scan","id":2}}
        self.outbox.enqueue(first,now=self.now); self.outbox.enqueue(second,now=self.now)
        client=Mock()
        from services.eddn_transport import EDDNDeliveryResult
        client.send.side_effect=(
            EDDNDeliveryResult(False,False,400,"bad"),
            EDDNDeliveryResult(True,False,200,"OK"),
        )
        worker=EDDNDeliveryWorker(self.outbox,client)
        self.assertEqual(worker.run_once(now=self.now),2)
        self.assertEqual(self.outbox.pending_count(),0)


if __name__=="__main__": unittest.main()
