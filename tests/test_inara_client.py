from unittest.mock import Mock
import unittest

import requests

from services.inara_client import InaraClient
from services.inara_credentials import InaraCredentials


class InaraClientTests(unittest.TestCase):
    def setUp(self):
        self.credentials=InaraCredentials("CMDR Test","F123","secret")
        self.event={"eventName":"setCommanderCredits",
                    "eventTimestamp":"2026-08-09T12:00:00Z",
                    "eventData":{"commanderCredits":10}}

    @staticmethod
    def response(status=200,payload=None):
        response=Mock(); response.status_code=status
        response.json.return_value=payload or {
            "header":{"eventStatus":200},"events":[{"eventStatus":200}]
        }
        return response

    def test_posts_official_header_and_translated_events(self):
        session=Mock(); session.post.return_value=self.response()
        result=InaraClient(session).submit(self.credentials,[self.event])
        self.assertTrue(result.accepted)
        call=session.post.call_args
        self.assertEqual(call.args[0],"https://inara.cz/inapi/v1/")
        payload=call.kwargs["json"]
        self.assertEqual(payload["header"]["appName"],"ODIN")
        self.assertEqual(payload["header"]["APIkey"],"secret")
        self.assertEqual(payload["header"]["commanderFrontierID"],"F123")
        self.assertTrue(payload["header"]["isBeingDeveloped"])
        self.assertEqual(payload["events"],[self.event])

    def test_warnings_and_soft_errors_are_processed(self):
        for status in (202,204):
            session=Mock(); session.post.return_value=self.response(payload={
                "header":{"eventStatus":200},"events":[{"eventStatus":status}]
            })
            self.assertTrue(InaraClient(session).submit(
                self.credentials,[self.event]
            ).accepted)

    def test_authorization_error_is_permanent(self):
        session=Mock(); session.post.return_value=self.response(payload={
            "header":{"eventStatus":400,"eventStatusText":"App not authorized"},
            "events":[],
        })
        result=InaraClient(session).submit(self.credentials,[self.event])
        self.assertFalse(result.accepted); self.assertFalse(result.retryable)

    def test_network_rate_limit_and_html_are_retryable(self):
        session=Mock(); session.post.side_effect=requests.ConnectionError("offline")
        self.assertTrue(InaraClient(session).submit(
            self.credentials,[self.event]
        ).retryable)
        response=self.response(403); response.json.side_effect=ValueError("HTML")
        session=Mock(); session.post.return_value=response
        self.assertTrue(InaraClient(session).submit(
            self.credentials,[self.event]
        ).retryable)


if __name__=="__main__": unittest.main()
