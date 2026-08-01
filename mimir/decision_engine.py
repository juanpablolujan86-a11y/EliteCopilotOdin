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
from mimir.discovery_context import DiscoveryContext


@dataclass(slots=True)
class ScientificDecision:
    """
    Resultado de una decisión científica de MÍMIR.
    """

    recommended: bool

    priority: str

    estimated_value: int

    minimum_estimated_value: int

    potential_first_logged_value: int

    minimum_potential_first_logged_value: int

    discovery_context: DiscoveryContext | None

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
        discovery_context: DiscoveryContext | None = None,
    ) -> ScientificDecision:
        """
        Evalúa las predicciones disponibles.

        Si no existen especies compatibles,
        recomienda no descender.
        """

        if not predictions:
            reasons = ["No se encontraron especies compatibles."]

            if discovery_context:
                reasons.extend(discovery_context.reasons())

            return ScientificDecision(
                recommended=False,
                priority="LOW",
                estimated_value=0,
                minimum_estimated_value=0,
                potential_first_logged_value=0,
                minimum_potential_first_logged_value=0,
                discovery_context=discovery_context,
                best_prediction=None,
                reasons=reasons,
            )

        best_prediction = predictions[0]

        best_value_by_genus: dict[str, int] = {}
        minimum_value_by_genus: dict[str, int] = {}

        for prediction in predictions:
            genus = prediction.species.genus
            best_value_by_genus[genus] = max(
                best_value_by_genus.get(genus, 0),
                prediction.species.value,
            )
            minimum_value_by_genus[genus] = min(
                minimum_value_by_genus.get(
                    genus,
                    prediction.species.value,
                ),
                prediction.species.value,
            )

        estimated_value = sum(best_value_by_genus.values())
        minimum_estimated_value = sum(minimum_value_by_genus.values())
        potential_first_logged_value = (
            estimated_value * 5
            if discovery_context
            and discovery_context.first_footfall_available
            else estimated_value
        )
        minimum_potential_first_logged_value = (
            minimum_estimated_value * 5
            if discovery_context
            and discovery_context.first_footfall_available
            else minimum_estimated_value
        )

        predictions_by_genus: dict[str, list[Prediction]] = {}

        for prediction in predictions:
            predictions_by_genus.setdefault(
                prediction.species.genus,
                [],
            ).append(prediction)

        prediction_reasons = ["Muestras biológicas probables:"]

        for genus, genus_predictions in predictions_by_genus.items():
            alternatives = " / ".join(
                f"{prediction.species.name} "
                f"({prediction.species.value:,} CR)"
                + (
                    " — variantes probables: "
                    + ", ".join(prediction.variants)
                    if prediction.variants
                    else ""
                )
                for prediction in genus_predictions
            )
            label = (
                f"{genus} — alternativas"
                if len(genus_predictions) > 1
                else genus
            )
            prediction_reasons.append(f"{label}: {alternatives}")

        reasons = [
            (
                "Especie principal compatible: "
                f"{best_prediction.species.name}"
            ),
            *prediction_reasons,
            (
                "Rango estimado total: "
                f"{minimum_estimated_value:,}–{estimated_value:,} CR"
                if minimum_estimated_value != estimated_value
                else f"Valor estimado total: {estimated_value:,} CR"
            ),
        ]

        if discovery_context:
            reasons.extend(discovery_context.reasons())

            if discovery_context.first_footfall_available:
                reasons.append(
                    "Valor potencial con primera catalogación: "
                    + (
                        f"{minimum_potential_first_logged_value:,}–"
                        f"{potential_first_logged_value:,} CR (×5)"
                        if minimum_potential_first_logged_value
                        != potential_first_logged_value
                        else f"{potential_first_logged_value:,} CR (×5)"
                    )
                )
                reasons.append(
                    "La bonificación First Logged es potencial y se "
                    "confirma al entregar las muestras."
                )

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
            minimum_estimated_value=minimum_estimated_value,
            potential_first_logged_value=potential_first_logged_value,
            minimum_potential_first_logged_value=(
                minimum_potential_first_logged_value
            ),
            discovery_context=discovery_context,
            best_prediction=best_prediction,
            reasons=reasons,
        )
