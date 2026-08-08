from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading
import unittest

from core.command_center import CommandCenter

class OfficerVoiceDispatchTests(unittest.TestCase):
    def test_fixed_response_uses_requested_officer(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center._voice_busy=threading.Event(); center._voice_busy.set()
        center.wake_listener=Mock()
        with patch("core.command_center.OfficerVoiceService") as service:
            center._run_fixed_voice_response("HEIMDALL","Ruta calculada.")
        service.return_value.speak.assert_called_once_with("HEIMDALL","Ruta calculada.")
        center.wake_listener.resume.assert_called_once()

if __name__=="__main__": unittest.main()
