"""Transforma decisiones científicas en recomendaciones para el comandante."""

from dataclasses import dataclass

from mimir.decision_engine import ScientificDecision


@dataclass(slots=True)
class ScientificRecommendation:
    title: str
    message: str
    priority: str
    reasons: list[str]


class ScientificRecommendationEngine:
    """Genera recomendaciones científicas legibles."""

    def build(
        self,
        decision: ScientificDecision,
    ) -> ScientificRecommendation:
        if not decision.recommended:
            return ScientificRecommendation(
                title="Descenso no recomendado",
                message=(
                    "Comandante, no se detectaron indicios científicos "
                    "suficientes para justificar un descenso."
                ),
                priority=decision.priority,
                reasons=decision.reasons,
            )

        best_prediction = decision.best_prediction

        if best_prediction is None:
            return ScientificRecommendation(
                title="Evaluación incompleta",
                message=(
                    "Comandante, el análisis científico no produjo una "
                    "especie principal."
                ),
                priority="LOW",
                reasons=decision.reasons,
            )

        value_text = f"{decision.estimated_value:,} créditos"

        if decision.minimum_estimated_value != decision.estimated_value:
            value_text = (
                f"entre {decision.minimum_estimated_value:,} y "
                f"{decision.estimated_value:,} créditos"
            )

        message = (
            "Comandante, las condiciones del planeta son compatibles con "
            f"{best_prediction.species.name}. El valor científico estimado "
            f"es de {value_text}. Recomiendo "
            "proceder con el descenso y realizar un reconocimiento biológico."
        )

        context = decision.discovery_context

        if context and context.first_footfall_available:
            potential_text = (
                f"{decision.potential_first_logged_value:,} créditos"
            )

            if (
                decision.minimum_potential_first_logged_value
                != decision.potential_first_logged_value
            ):
                potential_text = (
                    f"entre "
                    f"{decision.minimum_potential_first_logged_value:,} y "
                    f"{decision.potential_first_logged_value:,} créditos"
                )

            message += (
                " El Journal indica que la primera pisada todavía está "
                "disponible. Si las muestras obtienen First Logged, el "
                "valor potencial asciende a "
                f"{potential_text} (×5)."
            )

        return ScientificRecommendation(
            title="Descenso científico recomendado",
            message=message,
            priority=decision.priority,
            reasons=decision.reasons,
        )
