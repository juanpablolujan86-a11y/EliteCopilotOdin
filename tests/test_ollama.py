import unittest
from unittest.mock import Mock, patch

from intelligence.assistant import OdinLocalAssistant
from intelligence.ollama import OllamaClient, OllamaError


class OllamaClientTests(unittest.TestCase):
    @patch("intelligence.ollama.requests.post")
    def test_chat_uses_local_endpoint_and_disables_thinking_output(self, post: Mock):
        response = Mock()
        response.json.return_value = {"model": "gemma3:4b", "done": True, "message": {"content": "Sistemas operativos."}}
        post.return_value = response

        reply = OdinLocalAssistant(OllamaClient()).ask("Estado", context="Sistema: Sol")

        self.assertEqual(reply.text, "Sistemas operativos.")
        call = post.call_args
        self.assertEqual(call.args[0], "http://127.0.0.1:11434/api/chat")
        self.assertFalse(call.kwargs["json"]["think"])
        self.assertEqual(call.kwargs["json"]["options"]["num_ctx"], 4096)
        self.assertIn("Sistema: Sol", call.kwargs["json"]["messages"][1]["content"])

    @patch("intelligence.ollama.requests.post")
    def test_connection_failure_has_safe_message(self, post: Mock):
        import requests
        post.side_effect = requests.ConnectionError()
        with self.assertRaisesRegex(OllamaError, "no está disponible"):
            OdinLocalAssistant(OllamaClient()).ask("Estado")

    def test_empty_question_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "vacía"):
            OdinLocalAssistant(Mock()).ask("  ")


if __name__ == "__main__":
    unittest.main()
