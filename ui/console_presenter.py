"""
ODIN - Orbital Data Intelligence Nexus

console_presenter.py

Presenta en consola los eventos internos de ODIN.
"""

from models.events.recommendation_ready import RecommendationReady


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