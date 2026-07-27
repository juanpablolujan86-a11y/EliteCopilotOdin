"""
ODIN - Orbital Data Intelligence Nexus

console_presenter.py

Presenta en consola los eventos internos de ODIN.
"""

from models.events.recommendation_ready import RecommendationReady
from models.events.exploration_report_ready import (
    ExplorationReportReady,
)

class ConsolePresenter:
    """
    Muestra información útil en la consola.
    """

    def show_recommendation(
        self,
        recommendation: RecommendationReady,
    ) -> None:
        if not recommendation.message:
            return

        print()
        print("-" * 50)
        print(
            f"RECOMENDACIÓN ODIN "
            f"[{recommendation.priority}]"
        )
        print(recommendation.message)

        if recommendation.reasons:
            print("Motivos:")

            for reason in recommendation.reasons:
                print(f"  - {reason}")

        print("-" * 50)

    def show_exploration_report(
        self,
        report: ExplorationReportReady,
    ) -> None:
        print()
        print("=" * 50)
        print("INFORME DE EXPLORACIÓN ODIN")
        print("=" * 50)

        print(f"Sistema              : {report.system_name}")
        print(
            f"Cuerpos identificados: "
            f"{report.discovered_body_count}"
            f"/{report.expected_body_count or '?'}"
        )

        print(f"Estrellas            : {report.star_count}")
        print(f"Planetas             : {report.planet_count}")
        print(f"Lunas                : {report.moon_count}")
        print(
            f"Terraformables       : "
            f"{report.terraformable_count}"
        )
        print(f"Cartografiados       : {report.mapped_count}")
        print(
            f"Señales biológicas   : "
            f"{report.biology_signal_count}"
        )
        print(
            f"Muestras orgánicas   : "
            f"{report.organic_sample_count}"
        )

        status = (
            "Completa"
            if report.all_bodies_found
            else "En progreso"
        )

        print(f"Estado FSS           : {status}")

        if (
            report.all_bodies_found
            and report.expected_body_count
            and report.discovered_body_count
            < report.expected_body_count
        ):
            missing = (
                report.expected_body_count
                - report.discovered_body_count
            )

            print(
                "Sincronización       : "
                f"{missing} registro no recibido por ODIN"
            )

        print()
        print(
            f"RECOMENDACIÓN [{report.priority}]"
        )
        print(report.recommendation)

        if report.reasons:
            print("Motivos:")

            for reason in report.reasons:
                print(f"  - {reason}")

        print("=" * 50)