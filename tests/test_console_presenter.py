import io
import unittest
from contextlib import redirect_stdout

from models.events.exploration_report_ready import ExplorationReportReady
from models.events.recommendation_ready import RecommendationReady
from models.officer_report import OfficerReport
from models.events.organic_scan_updated import OrganicScanUpdated
from models.events.surface_navigation_updated import SurfaceNavigationUpdated
from ui.console_presenter import ConsolePresenter


class ConsolePresenterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.presenter = ConsolePresenter()

    def test_system_discovery_status_is_compact(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.presenter.show_recommendation(
                RecommendationReady(
                    priority="MEDIUM",
                    message="Sistema: Prueba\nEstado: registrado previamente en EDSM.",
                    reasons=["detalle interno"],
                )
            )

        visible = output.getvalue()
        self.assertTrue(visible.startswith("\033[2J\033[H"))
        self.assertIn("ESTADO DE DESCUBRIMIENTO", visible)
        self.assertIn("registrado previamente", visible)
        self.assertNotIn("detalle interno", visible)

    def test_fss_report_without_biology_is_hidden(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.presenter.show_exploration_report(
                ExplorationReportReady(
                    system_name="Prueba",
                    expected_body_count=11,
                    discovered_body_count=9,
                    star_count=1,
                    planet_count=8,
                    moon_count=0,
                    terraformable_count=0,
                    mapped_count=0,
                    biology_signal_count=0,
                    organic_sample_count=0,
                    all_bodies_found=True,
                    priority="LOW",
                    recommendation="Informe interno",
                )
            )

        self.assertEqual(output.getvalue(), "")

    def test_biology_shows_planet_genus_and_probable_species(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.presenter.show_scientific_report(
                OfficerReport(
                    officer="MÍMIR",
                    title="Informe extenso",
                    message="Explicación para voz",
                    priority="HIGH",
                    details=["regla interna"],
                    body_name="Prueba 4",
                    confirmed_genus_names=("Bacteria",),
                    probable_species=("Bacterium Informem",),
                    has_biological_signal=True,
                )
            )

        visible = output.getvalue()
        self.assertIn("Planeta              : Prueba 4", visible)
        self.assertIn("Géneros DSS          : Bacteria", visible)
        self.assertIn("Bacterium Informem", visible)
        self.assertNotIn("Explicación para voz", visible)
        self.assertNotIn("regla interna", visible)

    def test_environmental_prediction_without_signal_is_hidden(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.presenter.show_scientific_report(
                OfficerReport(
                    officer="MÍMIR",
                    title="Predicción preliminar",
                    message="Sólo para voz y log",
                    priority="HIGH",
                    details=[],
                    body_name="Prueba 2",
                    probable_species=("Stratum Tectonicas",),
                    has_biological_signal=False,
                )
            )

        self.assertEqual(output.getvalue(), "")

    def test_duplicate_biology_state_is_hidden(self) -> None:
        report = OfficerReport(
            officer="MÍMIR",
            title="Biología",
            message="",
            priority="HIGH",
            details=[],
            body_name="Prueba 4",
            confirmed_genus_names=("Bacteria",),
            probable_species=("Bacterium Aurasus",),
            has_biological_signal=True,
        )
        output = io.StringIO()
        with redirect_stdout(output):
            self.presenter.show_scientific_report(report)
            self.presenter.show_scientific_report(report)

        self.assertEqual(output.getvalue().count("Planeta"), 1)

    def test_organic_progress_and_distance_are_visible(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.presenter.show_organic_scan(
                OrganicScanUpdated(
                    body_id=7,
                    genus="Bacterium",
                    species="Bacterium Vesicula",
                    variant="Cyan",
                    scan_type="Log",
                    progress=1,
                    completed=False,
                    was_logged=False,
                    required_distance_m=500,
                )
            )
            self.presenter.show_surface_navigation(
                SurfaceNavigationUpdated(
                    genus="Bacterium",
                    species="Bacterium Vesicula",
                    progress=1,
                    distance_m=500,
                    required_distance_m=500,
                    ready_for_sample=True,
                )
            )

        visible = output.getvalue()
        self.assertIn("1/3", visible)
        self.assertIn("500 m", visible)
        self.assertIn("500/500 m", visible)
        self.assertIn("LISTA", visible)


if __name__ == "__main__":
    unittest.main()
