import unittest
from unittest.mock import Mock, patch

from intelligence.openai_client import OpenAIClient, OpenAIError


class OpenAIClientTests(unittest.TestCase):
    @patch("intelligence.openai_client.OpenAICredentialStore.get", return_value="secret")
    @patch("intelligence.openai_client.requests.post")
    def test_responses_request(self, post: Mock, _get: Mock):
        response = Mock(status_code=200)
        response.json.return_value = {"model": "gpt-5-mini", "output_text": "Operativo."}
        post.return_value = response
        reply = OpenAIClient().chat("Estado", system="Breve", context="Nave lista")
        self.assertEqual(reply.text, "Operativo.")
        payload = post.call_args.kwargs["json"]
        self.assertFalse(payload["store"])
        self.assertIn("Nave lista", payload["instructions"])

    @patch("intelligence.openai_client.OpenAICredentialStore.get", return_value=None)
    def test_missing_key(self, _get: Mock):
        with self.assertRaisesRegex(OpenAIError, "no está configurada"):
            OpenAIClient().chat("Estado")

    @patch("intelligence.openai_client.OpenAICredentialStore.get", return_value="secret")
    @patch("intelligence.openai_client.requests.post")
    def test_insufficient_quota_message(self, post: Mock, _get: Mock):
        response = Mock(status_code=429)
        response.json.return_value = {"error": {"code": "insufficient_quota"}}
        post.return_value = response
        with self.assertRaisesRegex(OpenAIError, "saldo o facturación"):
            OpenAIClient().chat("Estado")


if __name__ == "__main__":
    unittest.main()
