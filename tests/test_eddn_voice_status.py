import unittest

from core.command_center import CommandCenter
from services.eddn_outbox import EDDNOutboxSummary


class EDDNVoiceStatusTests(unittest.TestCase):
    def test_recognizes_natural_status_questions(self):
        for text in ("estado de EDDN","EDDN esta activo","funciona EDDN",
                     "cuantos envios tiene EDDN"):
            self.assertTrue(CommandCenter._is_eddn_status_request(text))

    def test_active_summary_contains_only_operational_counts(self):
        answer=CommandCenter._eddn_voice_summary(
            EDDNOutboxSummary(2,10,1,1,"commodity"),True,True
        )
        self.assertIn("transmisión a EDDN está activa",answer)
        self.assertIn("10 enviados",answer)
        self.assertIn("2 pendientes",answer)
        self.assertIn("1 rechazados",answer)
        self.assertIn("commodity",answer)

    def test_disabled_states_are_explained(self):
        empty=EDDNOutboxSummary(0,0,0,0,"")
        self.assertIn("captura",CommandCenter._eddn_voice_summary(empty,False,False))
        self.assertIn("transmisión está desactivada",
                      CommandCenter._eddn_voice_summary(empty,True,False))


if __name__=="__main__": unittest.main()
