# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
core.officer_dispatcher

Registro y despacho de eventos hacia los oficiales de ODIN.

Este componente decide qué oficial debe recibir cada tipo
de evento interno, sin conocer la implementación del oficial.
"""

from collections.abc import Callable
from typing import Any

from models.officer_report import OfficerReport


OfficerHandler = Callable[
    [dict[str, Any]],
    OfficerReport | None,
]


class OfficerDispatcher:
    """
    Distribuye eventos a los oficiales registrados.
    """

    def __init__(self) -> None:
        self._handlers: dict[
            str,
            list[OfficerHandler],
        ] = {}

    def register(
        self,
        event_type: str,
        handler: OfficerHandler,
    ) -> None:
        """
        Registra un oficial para un tipo de evento.
        """

        handlers = self._handlers.setdefault(
            event_type,
            [],
        )

        if handler not in handlers:
            handlers.append(handler)

    def unregister(
        self,
        event_type: str,
        handler: OfficerHandler,
    ) -> None:
        """
        Elimina un oficial de un tipo de evento.
        """

        handlers = self._handlers.get(
            event_type
        )

        if handlers is None:
            return

        if handler in handlers:
            handlers.remove(handler)

        if not handlers:
            del self._handlers[event_type]

    def dispatch(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[OfficerReport]:
        """
        Envía un evento a todos los oficiales registrados
        y devuelve los informes generados.
        """

        reports: list[OfficerReport] = []

        handlers = self._handlers.get(
            event_type,
            [],
        )

        for handler in handlers:
            report = handler(payload)

            if report is not None:
                reports.append(report)

        return reports

    def has_handlers(
        self,
        event_type: str,
    ) -> bool:
        """
        Indica si un evento tiene oficiales registrados.
        """

        return bool(
            self._handlers.get(event_type)
        )

    def registered_events(self) -> list[str]:
        """
        Devuelve los eventos que tienen oficiales registrados.
        """

        return sorted(
            self._handlers.keys()
        )