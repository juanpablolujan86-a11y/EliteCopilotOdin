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

    def test_wake_acknowledgement_uses_odin_and_resumes_listener(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center._voice_busy=threading.Event(); center._voice_busy.set()
        center._wake_acknowledgement_index=0
        center._wake_acknowledgement_lock=threading.Lock()
        center.wake_listener=Mock()
        with patch("core.command_center.OfficerVoiceService") as service:
            center._run_wake_acknowledgement()
        service.return_value.speak.assert_called_once_with("ODIN", "Sí, comandante?")
        self.assertFalse(center._voice_busy.is_set())
        center.wake_listener.resume.assert_called_once()

    def test_wake_acknowledgements_rotate_without_immediate_repetition(self):
        center=CommandCenter.__new__(CommandCenter)
        center._wake_acknowledgement_index=0
        center._wake_acknowledgement_lock=threading.Lock()

        phrases=[
            center._next_wake_acknowledgement()
            for _ in CommandCenter.WAKE_ACKNOWLEDGEMENTS
        ]

        self.assertEqual(tuple(phrases), CommandCenter.WAKE_ACKNOWLEDGEMENTS)
        self.assertEqual(
            center._next_wake_acknowledgement(),
            CommandCenter.WAKE_ACKNOWLEDGEMENTS[0],
        )

    def test_processing_messages_match_the_requested_context(self):
        self.assertEqual(
            CommandCenter._processing_message_for("qué biologías hay"),
            "Consultando los registros científicos.",
        )
        self.assertEqual(
            CommandCenter._processing_message_for("cuánto combustible tengo"),
            "Revisando los datos del comandante.",
        )
        self.assertEqual(
            CommandCenter._processing_message_for("datos de este sistema"),
            "Revisando la base de datos.",
        )

    def test_processing_message_signals_completion_without_resuming_listener(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center.wake_listener=Mock()
        completed=threading.Event()
        with patch("core.command_center.OfficerVoiceService") as service:
            center._run_processing_message("ODIN", "Procesando.", completed)
        service.return_value.speak.assert_called_once_with("ODIN", "Procesando.")
        self.assertTrue(completed.is_set())
        center.wake_listener.resume.assert_not_called()

    def test_answer_never_repeats_full_current_system_name(self):
        center=CommandCenter.__new__(CommandCenter)
        center.commander_state=SimpleNamespace(current_system="Synuefua QF-L d9-25")
        center.scientific_context=Mock()
        center.scientific_context.system_predictions.return_value={
            "Synuefua QF-L d9-25 1": ("Bacterium",)
        }

        answer=center._sanitize_current_system_references(
            "hay exobiología en este sistema",
            "Sí, en Synuefua QF-L d9-25 1.",
        )

        self.assertEqual(answer, "Sí, en planeta 1.")

        geology=center._sanitize_current_system_references(
            "hay geología en este sistema",
            "No tengo información geológica de Synuefua QF-L d9-25."
        )
        self.assertEqual(
            geology,
            "No tengo información geológica de este sistema.",
        )

        named=center._sanitize_current_system_references(
            "en qué sistema estoy",
            "Estás en Synuefua QF-L d9-25.",
        )
        self.assertEqual(named, "Estás en Synuefua QF-L d9-25.")

if __name__=="__main__": unittest.main()
