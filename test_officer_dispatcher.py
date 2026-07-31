# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
Prueba completa del Officer Dispatcher.
"""

from pathlib import Path

from core.officer_dispatcher import OfficerDispatcher
from mimir.officer_handler import MimirOfficerHandler
from mimir.scientific_officer import ScientificOfficer


ROOT = Path(__file__).resolve().parent

mimir = ScientificOfficer(
    species_file=ROOT / "knowledge" / "biology" / "species.json",
    rules_file=ROOT / "knowledge" / "biology" / "prediction_rules.json",
)

handler = MimirOfficerHandler(mimir)

dispatcher = OfficerDispatcher()

dispatcher.register(
    "planet_scan",
    handler.handle_planet_scan,
)

planet_scan = {
    "event": "Scan",
    "BodyName": "Planeta de prueba",
    "PlanetClass": "High metal content body",
    "AtmosphereType": "Carbon dioxide atmosphere",
    "SurfaceGravity": 3.138128,
    "SurfaceTemperature": 220.0,
    "Volcanism": "No volcanism",
}

reports = dispatcher.dispatch(
    "planet_scan",
    planet_scan,
)

assert len(reports) == 1, (
    "MÍMIR debía generar un informe para el evento Scan."
)

print("=" * 60)
print("ODIN - Officer Dispatcher Test")
print("=" * 60)

print()

print(
    "Cantidad de informes:",
    len(reports),
)

print()

for report in reports:

    print("Oficial")
    print("-------")
    print(report.officer)

    print()

    print("Título")
    print("------")
    print(report.title)

    print()

    print("Mensaje")
    print("--------")
    print(report.message)

    print()

    print("Prioridad")
    print("----------")
    print(report.priority)

    print()

    print("Detalles")
    print("---------")

    for detail in report.details:
        print("-", detail)

    print()
