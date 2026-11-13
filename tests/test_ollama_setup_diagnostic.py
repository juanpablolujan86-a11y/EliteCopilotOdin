import io
import logging
import queue
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from installer.ollama_gui import OllamaSetupWindow

class DiagnosticTests(unittest.TestCase):
    def test_full_error_without_final_newline_is_logged(self):
        window = OllamaSetupWindow.__new__(OllamaSetupWindow)
        window.messages = queue.Queue()
        window.cancelled = threading.Event()
        output = io.StringIO()
        window.logger = logging.Logger("diagnostic-test", logging.INFO)
        window.logger.addHandler(logging.StreamHandler(output))
        error = "Error: pull model manifest: " + "x" * 200 + " certificate rejected"
        process = Mock(stdout=io.StringIO(error))
        process.poll.return_value = 1
        process.wait.return_value = 1
        with patch("installer.ollama_gui.subprocess.Popen", return_value=process):
            with self.assertRaises(RuntimeError):
                window._pull_model(Path("ollama.exe"))
        self.assertIn(error, output.getvalue())
        self.assertIn("exit code: 1", output.getvalue())
        self.assertTrue(any(error in str(item) for item in list(window.messages.queue)))
