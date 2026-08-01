import logging
import tempfile
import unittest
from pathlib import Path

from core.diagnostics import MimirDiagnostics, OdinDiagnostics
from models.events.exploration_report_ready import ExplorationReportReady
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

    def test_hidden_fss_report_is_kept_in_odin_log(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            from core.diagnostics import configure_diagnostics

            configure_diagnostics(root)
            diagnostics = OdinDiagnostics()
            diagnostics.record_exploration_report(
                ExplorationReportReady(
                    system_name="Sistema de prueba",
                    expected_body_count=11,
                    discovered_body_count=11,
                    star_count=1,
                    planet_count=10,
                    moon_count=0,
                    terraformable_count=1,
                    mapped_count=0,
                    biology_signal_count=0,
                    organic_sample_count=0,
                    all_bodies_found=True,
                    priority="LOW",
                    recommendation="Informe oculto para voz",
                )
            )

            for handler in logging.getLogger().handlers:
                handler.flush()
            content = (root / "logs" / "odin.log").read_text("utf-8")
            self.assertIn("Sistema de prueba", content)
            self.assertIn("cuerpos=11/11", content)
            root_logger = logging.getLogger()
            for handler in list(root_logger.handlers):
                handler.close()
                root_logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
