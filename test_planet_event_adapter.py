# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
Prueba del adaptador de eventos planetarios de MÍMIR.
"""

from mimir.planet_event_adapter import PlanetEventAdapter


adapter = PlanetEventAdapter()

scan_event = {
    "event": "Scan",
    "BodyName": "Planeta de prueba",
    "PlanetClass": "High metal content body",
    "AtmosphereType": "Carbon dioxide atmosphere",
    "SurfaceGravity": 3.138128,
    "SurfaceTemperature": 220.0,
    "Volcanism": "No volcanism",
}

planet = adapter.from_scan_event(
    scan_event
)

print("=" * 60)
print("MÍMIR - Planet Event Adapter Test")
print("=" * 60)

print()
print("Evento original")
print("---------------")
print("Cuerpo      :", scan_event["BodyName"])
print("Clase       :", scan_event["PlanetClass"])
print("Atmósfera   :", scan_event["AtmosphereType"])
print("Gravedad    :", scan_event["SurfaceGravity"], "m/s²")
print(
    "Temperatura:",
    scan_event["SurfaceTemperature"],
    "K",
)
print("Volcanismo  :", scan_event["Volcanism"])

print()
print("Datos normalizados")
print("-------------------")
print("Tipo        :", planet["body_type"])
print("Atmósfera   :", planet["atmosphere"])
print("Gravedad    :", planet["gravity"], "g")
print("Temperatura :", planet["temperature"], "K")
print("Volcanismo  :", planet["volcanism"])