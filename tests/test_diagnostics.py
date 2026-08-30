import logging
import tempfile
import unittest
from pathlib import Path

from core.diagnostics import HeimdallDiagnostics, MimirDiagnostics, OdinDiagnostics
from heimdall.spansh import ExactRoutePlan, ExactWaypoint
from models.events.exploration_report_ready import ExplorationReportReady
from models.events.organic_scan_updated import OrganicScanUpdated
from models.officer_report import OfficerReport


class DiagnosticsTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        for logger_name in ("mimir.activity", "heimdall.activity", ""):
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

    def test_exact_route_can_be_logged_without_neutron_only_fields(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            diagnostics = HeimdallDiagnostics(root)
            plan = ExactRoutePlan(
                job_id="job-1",
                source_system="Origen",
                destination_system="Destino",
                waypoints=(
                    ExactWaypoint(
                        "Origen", 1, (0.0, 0.0, 0.0), 0.0, 40.0,
                        16.0, 0.0, True, False, False,
                    ),
                    ExactWaypoint(
                        "Destino", 2, (40.0, 0.0, 0.0), 40.0, 0.0,
                        12.0, 4.0, True, False, False,
                    ),
                ),
            )

            diagnostics.record_planned_route(plan)
            for handler in diagnostics.logger.handlers:
                handler.flush()

            content = (root / "logs" / "heimdall.log").read_text("utf-8")
            self.assertIn("estrategia=galaxy_exact", content)
            self.assertIn("alcance=0.00 ly", content)
            self.assertIn("eficiencia=n/a", content)
            for handler in list(diagnostics.logger.handlers):
                handler.close()
                diagnostics.logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
