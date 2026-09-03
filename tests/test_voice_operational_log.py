import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock

from core.command_center import CommandCenter


class VoiceOperationalLogTests(unittest.TestCase):
    def test_dictation_is_printed_once_before_cancel_response(self):
        center = object.__new__(CommandCenter)
        center.config = SimpleNamespace(language="es-419")
        center.wake_listener = Mock()
        center._voice_retry_pending = True

        output = io.StringIO()
        with redirect_stdout(output):
            center._start_voice_response("ODIN silencio")

        rendered = output.getvalue()
        self.assertIn("COMANDANTE: ODIN silencio", rendered)
        self.assertEqual(rendered.count("ODIN silencio"), 1)
        self.assertIn("ODIN: escucha cancelada.", rendered)
        center.wake_listener.resume.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
