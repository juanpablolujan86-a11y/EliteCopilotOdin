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

        if (
            context.first_visit
            and context.population == 0
            and not context.edsm_found
        ):
            return RecommendationReady(
                priority="HIGH",
                message=(
                    f"Comandante, {context.system_name} "
                    "no figura en nuestra memoria previa ni posee "
                    "información disponible en EDSM. "
                    "Esto indica una posible oportunidad de primer "
                    "descubrimiento, no una certeza. Recomiendo realizar "
                    "un escaneo completo."
                ),
                reasons=reasons,
            )

        if context.first_visit and context.population == 0:
            return RecommendationReady(
                priority="MEDIUM",
                message=(
                    f"Comandante, primera visita a "
                    f"{context.system_name}. "
                    "Es un sistema no habitado. "
                    "Recomiendo iniciar el FSS."
                ),
                reasons=reasons,
            )

        if context.first_visit:
            return RecommendationReady(
                priority="LOW",
                message=(
                    f"Comandante, primera visita registrada "
                    f"a {context.system_name}."
                ),
                reasons=reasons,
            )

        return RecommendationReady(
            priority="NONE",
            message="",
            reasons=reasons,
        )
