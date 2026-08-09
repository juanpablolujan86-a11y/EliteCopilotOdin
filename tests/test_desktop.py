import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.command_center import CommandCenter
from ui.desktop import GuiLogStream, OdinDesktopApp


class DesktopTests(unittest.TestCase):
    def test_log_stream_queues_complete_text_without_blocking(self) -> None:
        messages = queue.Queue()
        stream = GuiLogStream(messages)

        text = "HEIMDALL: ruta calculada\n"
        written = stream.write(text)

        self.assertEqual(written, len(text))
        self.assertEqual(messages.get_nowait(), text)

    def test_credit_format_matches_spanish_dashboard(self) -> None:
        self.assertEqual(OdinDesktopApp._credits(359520), "359.520 CR")
        self.assertEqual(OdinDesktopApp._credits(97300000, True), "≈ 97.300.000 CR")

    def test_gui_neutron_route_request_is_normalized_and_queued_once(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_route_requests = queue.Queue()
        center._route_calculation_busy = threading.Event()

        self.assertTrue(center.request_neutron_route("  Colonia   Dream  "))
        self.assertEqual(center._manual_route_requests.get_nowait(), "Colonia Dream")
        center._manual_route_requests.put("pending")
        self.assertFalse(center.request_neutron_route("Sol"))

    def test_mimir_dashboard_includes_real_signal_planets_without_predictions(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.commander_state = SimpleNamespace(system_address=42)
        center.database = Mock()
        center.database.query.side_effect = (
            [{
                "body_id": 5, "body_name": "Prueba 4 a",
                "source_event": "FSSBodySignals", "signal_type": "Biological",
                "signal_count": 2, "genus": None, "species": None,
            }],
            [{"body_id": 5, "body_name": "Prueba 4 a"}],
        )

        biology = center._dashboard_biology({})

        self.assertEqual(biology["bodies"], 1)
        self.assertEqual(biology["species"], 2)
        self.assertEqual(biology["details"][0]["body"], "Prueba 4 a")
        self.assertEqual(biology["details"][0]["signals"], 2)


if __name__ == "__main__":
    unittest.main()
