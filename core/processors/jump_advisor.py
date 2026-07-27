"""
ODIN - Orbital Data Intelligence Nexus

jump_advisor.py

Construye el contexto de exploración y publica
la recomendación generada por el DecisionEngine.
"""

from brain.decision_engine import DecisionEngine
from core.event_bus import EventBus
from core.internal_events import InternalEvent
from core.processors.exploration_context_builder import (
    ExplorationContextBuilder,
)


class JumpAdvisor:
    """
    Genera recomendaciones contextuales después de un salto FSD.
    """

    def __init__(
        self,
        context_builder: ExplorationContextBuilder,
        decision_engine: DecisionEngine,
        event_bus: EventBus,
    ) -> None:
        self.context_builder = context_builder
        self.decision_engine = decision_engine
        self.event_bus = event_bus

    def handle(self, event: dict) -> None:
        context = self.context_builder.build(event)

        recommendation = (
            self.decision_engine.evaluate_exploration(context)
        )

        if not recommendation.message:
            return

        self.event_bus.publish_internal(
            InternalEvent.RECOMMENDATION_READY,
            recommendation,
        )