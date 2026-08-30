"""Transforma decisiones científicas en recomendaciones para el comandante."""

from dataclasses import dataclass

from mimir.decision_engine import ScientificDecision
from core.localization import normalize_language, text


@dataclass(slots=True)
class ScientificRecommendation:
    title: str
    message: str
    priority: str
    reasons: list[str]


class ScientificRecommendationEngine:
    """Genera recomendaciones científicas legibles."""

    def __init__(self, language: str = "es-419") -> None:
        self.language = normalize_language(language)

    def _t(self, key: str, **values) -> str:
        return text(key, self.language, **values)

    def build(
        self,
        decision: ScientificDecision,
    ) -> ScientificRecommendation:
        if not decision.recommended:
            return ScientificRecommendation(
                title=self._t("mimir.descent_not_recommended"),
                message=self._t("mimir.no_evidence"),
                priority=decision.priority,
                reasons=decision.reasons,
            )

        best_prediction = decision.best_prediction

        if best_prediction is None:
            return ScientificRecommendation(
                title=self._t("mimir.incomplete"),
                message=self._t("mimir.no_primary"),
                priority="LOW",
                reasons=decision.reasons,
            )

        value_text = self._t("mimir.value", value=f"{decision.estimated_value:,}")

        if decision.minimum_estimated_value != decision.estimated_value:
            value_text = self._t(
                "mimir.value_range",
                minimum=f"{decision.minimum_estimated_value:,}",
                maximum=f"{decision.estimated_value:,}",
            )

        message = self._t(
            "mimir.recommend", species=best_prediction.species.name,
            value=value_text,
        )

        context = decision.discovery_context

        if context and context.first_footfall_available:
            potential_text = self._t(
                "mimir.value", value=f"{decision.potential_first_logged_value:,}"
            )

            if (
                decision.minimum_potential_first_logged_value
                != decision.potential_first_logged_value
            ):
                potential_text = self._t(
                    "mimir.value_range",
                    minimum=f"{decision.minimum_potential_first_logged_value:,}",
                    maximum=f"{decision.potential_first_logged_value:,}",
                )

            message += self._t("mimir.first_logged", value=potential_text)

        return ScientificRecommendation(
            title=self._t("mimir.descent_recommended"),
            message=message,
            priority=decision.priority,
            reasons=decision.reasons,
        )
