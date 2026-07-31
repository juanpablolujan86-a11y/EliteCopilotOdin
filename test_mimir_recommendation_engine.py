# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
Prueba completa del flujo científico de MÍMIR.
"""

from pathlib import Path

from mimir.decision_engine import ScientificDecisionEngine
from mimir.recommendation_engine import (
    ScientificRecommendationEngine,
)
from mimir.species_predictor import SpeciesPredictor


ROOT = Path(__file__).resolve().parent

predictor = SpeciesPredictor(
    species_file=ROOT / "knowledge" / "biology" / "species.json",
    rules_file=ROOT / "knowledge" / "biology" / "prediction_rules.json",
)

decision_engine = ScientificDecisionEngine()

recommendation_engine = ScientificRecommendationEngine()

planet = {
    "atmosphere": "CarbonDioxide",
    "body_type": "High metal content body",
    "gravity": 0.32,
    "temperature": 220.0,
}

predictions = predictor.predict(
    planet
)

decision = decision_engine.decide(
    predictions
)

recommendation = recommendation_engine.build(
    decision
)

print("=" * 60)
print("MÍMIR - Complete Scientific Analysis")
print("=" * 60)

print()

print("Título")
print("------")
print(recommendation.title)

print()

print("Mensaje")
print("--------")
print(recommendation.message)

print()

print("Prioridad")
print("----------")
print(recommendation.priority)

print()

print("Motivos")
print("--------")

for reason in recommendation.reasons:
    print("-", reason)