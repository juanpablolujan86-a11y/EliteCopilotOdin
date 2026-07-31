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

from core.event_bus import EventBus
from core.internal_events import InternalEvent
from mimir.officer_handler import MimirOfficerHandler
from models.events.planet_scan_ready import PlanetScanReady


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

        report = self.handler.handle_planet_scan(
            event.event,
        )

        if report is None:
            return

        self.event_bus.publish_internal(
            InternalEvent.SCIENTIFIC_ANALYSIS_READY,
            report,
        )