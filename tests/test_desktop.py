import queue
import threading
import unittest

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


if __name__ == "__main__":
    unittest.main()
