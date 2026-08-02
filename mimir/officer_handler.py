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
from mimir.discovery_context import DiscoveryContext


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
        confirmed_genus_ids: tuple[str, ...] = (),
        confirmed_genus_names: tuple[str, ...] = (),
        has_biological_signal: bool = False,
        system_population: int = 0,
        scientific_context: dict[str, Any] | None = None,
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
                payload,
                scientific_context=scientific_context,
            )
        )

        discovery_context = DiscoveryContext.from_scan_event(
            payload,
            system_population=system_population,
        )

        predictions = self.officer.predict_species(
            planet,
            confirmed_genus_ids=confirmed_genus_ids,
        )

        # Un análisis ambiental sin candidatos no aporta una decisión útil y
        # llenaba la consola durante el FSS. Si el DSS confirmó un género,
        # conservamos el informe aunque la especie todavía sea indeterminada.
        if not predictions and not confirmed_genus_ids:
            return None

        recommendation = (
            self.officer.analyze_planet(
                planet,
                confirmed_genus_ids=confirmed_genus_ids,
                discovery_context=discovery_context,
            )
        )

        body_name = payload.get(
            "BodyName",
            "Cuerpo desconocido",
        )

        details = [
            f"Cuerpo analizado: {body_name}",
            (
                "Nivel de evidencia: géneros confirmados por DSS"
                if confirmed_genus_ids
                else "Nivel de evidencia: predicción ambiental preliminar"
            ),
            *recommendation.reasons,
        ]

        predicted_genus_ids = {
            prediction.species.genus_codex_id
            for prediction in predictions
        }
        unresolved_genus_names = [
            name
            for genus_id, name in zip(
                confirmed_genus_ids,
                confirmed_genus_names,
            )
            if genus_id not in predicted_genus_ids
        ]

        if unresolved_genus_names:
            unresolved = ", ".join(unresolved_genus_names)
            details.append(
                "Género confirmado con especie todavía indeterminada: "
                + unresolved
            )
            recommendation.message += (
                " El DSS también confirmó "
                f"{unresolved}, pero MÍMIR todavía no puede determinar "
                "su especie con las condiciones conocidas."
            )

        if confirmed_genus_names:
            details.insert(
                1,
                "Género confirmado por DSS: "
                + ", ".join(confirmed_genus_names),
            )

        return OfficerReport(
            officer="MÍMIR",
            title=recommendation.title,
            message=recommendation.message,
            priority=recommendation.priority,
            details=details,
            body_name=str(body_name),
            confirmed_genus_names=confirmed_genus_names,
            probable_species=tuple(
                dict.fromkeys(
                    prediction.species.name
                    for prediction in predictions
                )
            ),
            has_biological_signal=has_biological_signal,
        )
