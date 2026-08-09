import queue
import unittest

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


if __name__ == "__main__":
    unittest.main()
