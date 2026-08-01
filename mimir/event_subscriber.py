# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 5 - Integración
# ============================================================

"""
event_subscriber.py

Integra MÍMIR con el EventBus de ODIN.

Escucha los eventos planetarios, ejecuta el análisis
científico y publica el resultado para el resto
del sistema.
"""

import logging

from core.event_bus import EventBus
from core.internal_events import InternalEvent
from mimir.officer_handler import MimirOfficerHandler
from models.events.planet_scan_ready import PlanetScanReady


logger = logging.getLogger("mimir.activity")


class MimirEventSubscriber:
    """
    Suscriptor del EventBus para MÍMIR.
    """

    def __init__(
        self,
        event_bus: EventBus,
        handler: MimirOfficerHandler,
    ) -> None:

        self.event_bus = event_bus
        self.handler = handler

        self.event_bus.subscribe(
            InternalEvent.PLANET_SCAN_READY,
            self.handle_planet_scan,
        )

    def handle_planet_scan(
        self,
        event: PlanetScanReady,
    ) -> None:
        """
        Ejecuta el análisis científico del planeta.
        """

        body_name = event.event.get("BodyName", "Cuerpo desconocido")
        logger.info(
            "EVALUACIÓN | cuerpo=%s | géneros_DSS=%s",
            body_name,
            ", ".join(event.confirmed_genus_names) or "sin confirmar",
        )

        try:
            report = self.handler.handle_planet_scan(
                event.event,
                confirmed_genus_ids=event.confirmed_genus_ids,
                confirmed_genus_names=event.confirmed_genus_names,
                system_population=event.system_population,
                scientific_context=event.scientific_context,
            )
        except Exception:
            logger.exception("FALLO | cuerpo=%s", body_name)
            raise

        if report is None:
            logger.info("RESULTADO | cuerpo=%s | sin interés biológico", body_name)
            return

        self.event_bus.publish_internal(
            InternalEvent.SCIENTIFIC_ANALYSIS_READY,
            report,
        )
