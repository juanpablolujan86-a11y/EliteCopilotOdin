# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
mimir.scientific_officer

Punto de entrada principal del Oficial Científico MÍMIR.

Coordina:

- Predicción de especies.
- Decisión científica.
- Generación de recomendaciones.
"""

from pathlib import Path
from typing import Any

from mimir.decision_engine import ScientificDecision
from mimir.decision_engine import ScientificDecisionEngine
from mimir.recommendation_engine import ScientificRecommendation
from mimir.recommendation_engine import (
    ScientificRecommendationEngine,
)
from mimir.species_predictor import SpeciesPredictor
from models.prediction import Prediction
from mimir.discovery_context import DiscoveryContext


class ScientificOfficer:
    """
    Fachada principal del Oficial Científico MÍMIR.

    El resto de ODIN utilizará esta clase y no accederá
    directamente a los motores internos del oficial.
    """

    def __init__(
        self,
        species_file: Path,
        rules_file: Path,
        minimum_value: int = 1_000_000,
    ) -> None:
        self.predictor = SpeciesPredictor(
            species_file=species_file,
            rules_file=rules_file,
        )

        self.decision_engine = ScientificDecisionEngine(
            minimum_value=minimum_value,
        )

        self.recommendation_engine = (
            ScientificRecommendationEngine()
        )

    def predict_species(
        self,
        planet: dict[str, Any],
        confirmed_genus_ids: tuple[str, ...] = (),
    ) -> list[Prediction]:
        """
        Predice las especies compatibles con un planeta.
        """

        return self.predictor.predict(
            planet,
            confirmed_genus_ids=confirmed_genus_ids,
        )

    def make_decision(
        self,
        predictions: list[Prediction],
        discovery_context: DiscoveryContext | None = None,
    ) -> ScientificDecision:
        """
        Convierte las predicciones en una decisión científica.
        """

        return self.decision_engine.decide(
            predictions,
            discovery_context=discovery_context,
        )

    def build_recommendation(
        self,
        decision: ScientificDecision,
    ) -> ScientificRecommendation:
        """
        Convierte la decisión en una recomendación legible.
        """

        return self.recommendation_engine.build(
            decision
        )

    def analyze_planet(
        self,
        planet: dict[str, Any],
        confirmed_genus_ids: tuple[str, ...] = (),
        discovery_context: DiscoveryContext | None = None,
    ) -> ScientificRecommendation:
        """
        Ejecuta el análisis científico completo.

        Planeta
            ↓
        Predicciones
            ↓
        Decisión
            ↓
        Recomendación
        """

        predictions = self.predict_species(
            planet,
            confirmed_genus_ids=confirmed_genus_ids,
        )

        decision = self.make_decision(
            predictions,
            discovery_context=discovery_context,
        )

        return self.build_recommendation(
            decision
        )
