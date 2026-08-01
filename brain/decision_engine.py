"""
ODIN - Orbital Data Intelligence Nexus

decision_engine.py

Analiza el contexto reunido por ODIN y genera
recomendaciones útiles para el comandante.
"""

from models.events.recommendation_ready import RecommendationReady
from models.exploration_context import ExplorationContext


class DecisionEngine:
    """
    Motor de decisiones basado en reglas.
    """

    def evaluate_exploration(
        self,
        context: ExplorationContext,
    ) -> RecommendationReady:
        """
        Evalúa el contexto de exploración de un sistema.
        """

        reasons = []

        if context.first_visit:
            reasons.append(
                "Primera visita registrada por ODIN"
            )

        if context.population == 0:
            reasons.append(
                "Sistema no habitado"
            )

        if not context.edsm_found:
            reasons.append(
                "EDSM no posee información del sistema"
            )

        if context.edsm_found:
            return RecommendationReady(
                priority="MEDIUM",
                message=(
                    f"Sistema: {context.system_name}\n"
                    "Estado: registrado previamente en EDSM por otro comandante."
                ),
                reasons=["EDSM posee información pública del sistema"],
            )

        if not context.edsm_found:
            return RecommendationReady(
                priority="HIGH",
                message=(
                    f"Sistema: {context.system_name}\n"
                    "Estado: sin registro disponible en EDSM. "
                    "Posible primer descubrimiento; no es una certeza."
                ),
                reasons=reasons,
            )
