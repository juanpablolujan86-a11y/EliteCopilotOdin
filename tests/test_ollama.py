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
    def test_chat_falls_back_to_generate_when_chat_endpoint_is_missing(self, post: Mock):
        missing = Mock(status_code=404)
        generated = Mock(status_code=200)
        generated.raise_for_status.return_value = None
        generated.json.return_value = {
            "model": "gemma3:4b", "done": True,
            "response": "Conexión correcta.",
        }
        post.side_effect = (missing, generated)

        reply = OllamaClient().chat(
            "Estado", system="Sos ODIN", context="Sistema: Sol"
        )

        self.assertEqual(reply.text, "Conexión correcta.")
        self.assertEqual(post.call_args_list[1].args[0], "http://127.0.0.1:11434/api/generate")
        fallback_prompt = post.call_args_list[1].kwargs["json"]["prompt"]
        self.assertIn("Sos ODIN", fallback_prompt)
        self.assertIn("Sistema: Sol", fallback_prompt)

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
