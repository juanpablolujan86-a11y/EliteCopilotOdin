# ============================================================
# ODIN
#
# Versión : 0.2.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
mimir.officer_handler

Adaptador entre el OfficerDispatcher y MÍMIR.

Recibe eventos Scan reales del Journal, normaliza sus datos,
ejecuta el análisis científico y devuelve un OfficerReport.
"""

from typing import Any

from mimir.planet_event_adapter import PlanetEventAdapter
from mimir.scientific_officer import ScientificOfficer
from models.officer_report import OfficerReport


class MimirOfficerHandler:
    """
    Convierte eventos del Journal en informes de MÍMIR.
    """

    def __init__(
        self,
        officer: ScientificOfficer,
    ) -> None:
        self.officer = officer
        self.planet_adapter = PlanetEventAdapter()

    def handle_planet_scan(
        self,
        payload: dict[str, Any],
    ) -> OfficerReport | None:
        """
        Procesa un evento Scan planetario y devuelve
        un informe científico para ODIN.
        """

        planet_class = payload.get(
            "PlanetClass"
        )

        if not planet_class:
            return None

        planet = (
            self.planet_adapter.from_scan_event(
                payload
            )
        )

        recommendation = (
            self.officer.analyze_planet(
                planet
            )
        )

        body_name = payload.get(
            "BodyName",
            "Cuerpo desconocido",
        )

        details = [
            f"Cuerpo analizado: {body_name}",
            *recommendation.reasons,
        ]

        return OfficerReport(
            officer="MÍMIR",
            title=recommendation.title,
            message=recommendation.message,
            priority=recommendation.priority,
            details=details,
        )