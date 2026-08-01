# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
mimir.decision_engine

Evalúa las predicciones científicas y determina
si vale la pena recomendar un descenso planetario.
"""

from dataclasses import dataclass

from models.prediction import Prediction


@dataclass(slots=True)
class ScientificDecision:
    """
    Resultado de una decisión científica de MÍMIR.
    """

    recommended: bool

    priority: str

    estimated_value: int

    best_prediction: Prediction | None

    reasons: list[str]


class ScientificDecisionEngine:
    """
    Convierte predicciones biológicas en una
    decisión útil para el comandante.
    """

    def __init__(
        self,
        minimum_value: int = 1_000_000,
    ) -> None:
        self.minimum_value = minimum_value

    def decide(
        self,
        predictions: list[Prediction],
    ) -> ScientificDecision:
        """
        Evalúa las predicciones disponibles.

        Si no existen especies compatibles,
        recomienda no descender.
        """

        if not predictions:
            return ScientificDecision(
                recommended=False,
                priority="LOW",
                estimated_value=0,
                best_prediction=None,
                reasons=[
                    "No se encontraron especies compatibles.",
                ],
            )

        best_prediction = predictions[0]

        best_value_by_genus: dict[str, int] = {}

        for prediction in predictions:
            genus = prediction.species.genus
            best_value_by_genus[genus] = max(
                best_value_by_genus.get(genus, 0),
                prediction.species.value,
            )

        estimated_value = sum(best_value_by_genus.values())

        reasons = [
            (
                "Especie principal compatible: "
                f"{best_prediction.species.name}"
            ),
            (
                "Valor estimado total: "
                f"{estimated_value:,} CR"
            ),
        ]

        if estimated_value >= 10_000_000:
            priority = "HIGH"

        elif estimated_value >= self.minimum_value:
            priority = "MEDIUM"

        else:
            priority = "LOW"

        recommended = (
            estimated_value
            >= self.minimum_value
        )

        if recommended:
            reasons.append(
                "El valor científico supera el "
                "mínimo operativo configurado."
            )

        else:
            reasons.append(
                "El valor científico no supera el "
                "mínimo operativo configurado."
            )

        return ScientificDecision(
            recommended=recommended,
            priority=priority,
            estimated_value=estimated_value,
            best_prediction=best_prediction,
            reasons=reasons,
        )
