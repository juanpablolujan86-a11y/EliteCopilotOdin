"""
ODIN
Orbital Data Intelligence Nexus

RecommendationReady

Representa una recomendación generada por
el Decision Engine.
"""

from dataclasses import dataclass, field


@dataclass
class RecommendationReady:
    """
    Evento interno generado por el cerebro de ODIN.
    """

    priority: str

    message: str

    reasons: list[str] = field(default_factory=list)