# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
mimir.recommendation_engine

Transforma una decisión científica en una recomendación
clara para el comandante.
"""

from dataclasses import dataclass

from mimir.decision_engine import ScientificDecision


@dataclass(slots=True)
class ScientificRecommendation:
    """
    Recomendación final emitida por MÍMIR.
    """

    title: str

    message: str

    priority: str

    reasons: list[str]


class ScientificRecommendationEngine:
    """
    Genera recomendaciones científicas legibles
    a partir de decisiones de MÍMIR.
    """

    def build(
        self,
        decision: ScientificDecision,
    ) -> ScientificRecommendation:
        """
        Convierte una decisión científica en una
        recomendación para el comandante.
        """

        if not decision.recommended:
            return ScientificRecommendation(
                title="Descenso no recomendado",
                message=(
                    "Comandante, no se detectaron "
                    "indicios científicos suficientes "
                    "para justificar un descenso."
                ),
                priority=decision.priority,
                reasons=decision.reasons,
            )

        best_prediction = decision.best_prediction

        if best_prediction is None:
            return ScientificRecommendation(
                title="Evaluación incompleta",
                message=(
                    "Comandante, el análisis científico "
                    "no produjo una especie principal."
                ),
                priority="LOW",
                reasons=decision.reasons,
            )

        message = (
            "Comandante, las condiciones del planeta "
            f"son compatibles con "
            f"{best_prediction.species.name}. "
            f"El valor científico estimado es de "
            f"{decision.estimated_value:,} créditos. "
            "Recomiendo proceder con el descenso "
            "y realizar un reconocimiento biológico."
        )

        return ScientificRecommendation(
            title="Descenso científico recomendado",
            message=message,
            priority=decision.priority,
            reasons=decision.reasons,
        )