from unittest.mock import Mock
import unittest

import requests

from services.edsm_credentials import EDSMCredentials
from services.edsm_journal import EDSMJournalClient


class EDSMJournalClientTests(unittest.TestCase):
    def setUp(self):
        self.credentials=EDSMCredentials("CMDR Test","secret-key")
        self.event={"timestamp":"2026-08-09T12:00:00Z","event":"FSDJump",
                    "StarSystem":"Sol","FuelLevel":12.5}

    @staticmethod
    def response(status=200,payload=None):
        response=Mock(); response.status_code=status
        response.json.return_value=payload if payload is not None else {"msgnum":100,"msg":"OK"}
        return response

    def test_posts_unmodified_journal_batch_to_official_endpoint(self):
        session=Mock(); session.post.return_value=self.response()
        result=EDSMJournalClient(session).submit(
            self.credentials,[self.event],game_version="4.1.3",game_build="r1"
        )
        self.assertTrue(result.accepted)
        call=session.post.call_args
        self.assertEqual(call.args[0],"https://www.edsm.net/api-journal-v1")
        payload=call.kwargs["json"]
        self.assertEqual(payload["commanderName"],"CMDR Test")
        self.assertEqual(payload["apiKey"],"secret-key")
        self.assertEqual(payload["message"],[self.event])
        self.assertEqual(payload["message"][0]["FuelLevel"],12.5)

    def test_duplicate_and_old_codes_are_treated_as_processed(self):
        for code in (101,102,103,104):
            session=Mock(); session.post.return_value=self.response(
                payload={"msgnum":code,"msg":"procesado"}
            )
            result=EDSMJournalClient(session).submit(
                self.credentials,[self.event],game_version="4.1",game_build="r1"
            )
            self.assertTrue(result.accepted)

    def test_invalid_credentials_are_permanent_failure(self):
        session=Mock(); session.post.return_value=self.response(
            payload={"msgnum":203,"msg":"credenciales invalidas"}
        )
        result=EDSMJournalClient(session).submit(
            self.credentials,[self.event],game_version="4.1",game_build="r1"
        )
        self.assertFalse(result.accepted); self.assertFalse(result.retryable)

    def test_network_and_rate_limit_failures_are_retryable(self):
        session=Mock(); session.post.side_effect=requests.ConnectionError("sin red")
        result=EDSMJournalClient(session).submit(
            self.credentials,[self.event],game_version="4.1",game_build="r1"
        )
        self.assertTrue(result.retryable)
        session=Mock(); session.post.return_value=self.response(429,{"msgnum":429})
        result=EDSMJournalClient(session).submit(
            self.credentials,[self.event],game_version="4.1",game_build="r1"
        )
        self.assertTrue(result.retryable)

    def test_rejects_empty_oversized_or_legacy_batches_before_network(self):
        client=EDSMJournalClient(Mock())
        with self.assertRaises(ValueError):
            client.submit(self.credentials,[],game_version="4.1",game_build="r1")
        with self.assertRaises(ValueError):
            client.submit(self.credentials,[self.event]*101,game_version="4.1",game_build="r1")
        with self.assertRaises(ValueError):
            client.submit(self.credentials,[self.event],game_version="3.8.0",game_build="r1")
        with self.assertRaises(ValueError):
            client.submit(self.credentials,[self.event],game_version="4.1",game_build="")


if __name__=="__main__": unittest.main()
