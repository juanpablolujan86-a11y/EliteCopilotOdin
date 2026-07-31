# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
test_mimir_decision_engine.py

Prueba el flujo completo de predicción y decisión científica.
"""

from pathlib import Path

from mimir.decision_engine import ScientificDecisionEngine
from mimir.species_predictor import SpeciesPredictor


ROOT = Path(__file__).resolve().parent

predictor = SpeciesPredictor(
    species_file=(
        ROOT
        / "knowledge"
        / "biology"
        / "species.json"
    ),
    rules_file=(
        ROOT
        / "knowledge"
        / "biology"
        / "prediction_rules.json"
    ),
)

decision_engine = ScientificDecisionEngine(
    minimum_value=1_000_000,
)

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

print("=" * 60)
print("MÍMIR - Scientific Decision Test")
print("=" * 60)

print()
print("Predicciones compatibles:", len(predictions))
print("Descenso recomendado     :", decision.recommended)
print("Prioridad                :", decision.priority)
print(
    "Valor estimado          : "
    f"{decision.estimated_value:,} CR"
)

print()

if decision.best_prediction is not None:
    print(
        "Especie principal       : "
        f"{decision.best_prediction.species.name}"
    )

print()
print("Motivos:")

for reason in decision.reasons:
    print(f"  - {reason}")