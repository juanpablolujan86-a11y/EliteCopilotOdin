import logging
import tempfile
import unittest
from pathlib import Path

from core.diagnostics import MimirDiagnostics
from models.events.organic_scan_updated import OrganicScanUpdated
from models.officer_report import OfficerReport


class DiagnosticsTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        for logger_name in ("mimir.activity", ""):
            logger = logging.getLogger(logger_name)
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)

    def test_mimir_activity_is_written_to_its_own_log(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            diagnostics = MimirDiagnostics(root)
            diagnostics.record_scientific_report(
                OfficerReport(
                    officer="MÍMIR",
                    title="Descenso recomendado",
                    message="Bacteria probable",
                    priority="HIGH",
                    details=["Cuerpo analizado: Prueba 1"],
                )
            )

            content = (root / "logs" / "mimir.log").read_text("utf-8")
            self.assertIn("Bacteria probable", content)
            self.assertIn("Cuerpo analizado: Prueba 1", content)
            diagnostics.close()

    def test_organic_progress_is_written_without_optional_body_name(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            diagnostics = MimirDiagnostics(root)
            diagnostics.record_organic_scan(
                OrganicScanUpdated(
                    body_id=7,
                    genus="Bacterium",
                    species="Bacterium Informem",
                    variant="Lime",
                    scan_type="Sample",
                    progress=2,
                    completed=False,
                    was_logged=False,
                )
            )

            content = (root / "logs" / "mimir.log").read_text("utf-8")
            self.assertIn("body_id=7", content)
            self.assertIn("progreso=2/3", content)
            diagnostics.close()


if __name__ == "__main__":
    unittest.main()
