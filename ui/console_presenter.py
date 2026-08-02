"""Presentación mínima de ODIN durante el vuelo."""

from models.events.exploration_report_ready import ExplorationReportReady
from models.events.organic_scan_updated import OrganicScanUpdated
from models.events.recommendation_ready import RecommendationReady
from models.officer_report import OfficerReport


class ConsolePresenter:
    """Muestra sólo información inmediata para el comandante."""

    def __init__(self) -> None:
        self._shown_biology_states: set[tuple] = set()

    def show_organic_scan(self, scan: OrganicScanUpdated) -> None:
        """El progreso se conserva en el log para la futura salida por voz."""

        return None

    def show_recommendation(
        self,
        recommendation: RecommendationReady,
    ) -> None:
        if not recommendation.message:
            return

        # Cada salto reemplaza el sistema anterior en lugar de acumularlo.
        self._shown_biology_states.clear()
        print("\033[2J\033[H", end="")
        print("-" * 50)
        print("ESTADO DE DESCUBRIMIENTO")
        print(recommendation.message)
        print("-" * 50)

    def show_exploration_report(
        self,
        report: ExplorationReportReady,
    ) -> None:
        """Avisa únicamente qué planetas poseen señales biológicas."""

        if not report.biological_bodies:
            return

        new_bodies = [
            body_name
            for body_name in report.biological_bodies
            if (body_name, "pendiente_dss")
            not in self._shown_biology_states
        ]
        if not new_bodies:
            return

        print()
        print("=" * 50)
        print("BIOLOGÍA DETECTADA")
        for body_name in new_bodies:
            state = (body_name, "pendiente_dss")
            self._shown_biology_states.add(state)
            print(f"Planeta              : {body_name}")
            print("Tipo probable        : pendiente de escaneo DSS")
        print("=" * 50)

    def show_scientific_report(
        self,
        report: OfficerReport,
    ) -> None:
        """Muestra planeta, géneros DSS y especies probables."""

        if not report.has_biological_signal:
            return

        state = (
            report.body_name,
            report.confirmed_genus_names,
            report.probable_species,
        )
        if state in self._shown_biology_states:
            return
        self._shown_biology_states.add(state)

        print()
        print("=" * 50)
        print("BIOLOGÍA DETECTADA")
        print(f"Planeta              : {report.body_name or 'Desconocido'}")

        if report.confirmed_genus_names:
            print(
                "Géneros DSS          : "
                + ", ".join(report.confirmed_genus_names)
            )

        if report.probable_species:
            print("Especies probables:")
            for species in report.probable_species:
                print(f"  - {species}")

        print("=" * 50)
