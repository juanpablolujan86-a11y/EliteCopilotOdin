"""
ODIN - Orbital Data Intelligence Nexus

event_bus.py

Distribuye eventos externos de Elite Dangerous
y eventos internos generados por ODIN.
"""

import logging
import sys
from contextlib import redirect_stdout
from io import StringIO


logger = logging.getLogger("odin.events")


class EventBus:
    """
    Centro de comunicaciones de ODIN.
    """

    def __init__(self) -> None:
        self.subscribers: dict[str, list] = {}
        self.output_stream = sys.stdout

    def subscribe(self, event_name: str, callback) -> None:
        """
        Registra una función para recibir un evento.
        """

        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        self.subscribers[event_name].append(callback)

    def publish(self, event: dict) -> None:
        """
        Publica un evento externo proveniente del Journal.
        """

        event_name = event.get("event")

        if not event_name:
            return

        self.publish_internal(event_name, event)

    def publish_internal(
        self,
        event_name: str,
        payload,
    ) -> None:
        """
        Publica un evento interno generado por ODIN.
        """

        callbacks = self.subscribers.get(event_name, [])

        for callback in callbacks:
            callback_module = str(getattr(callback, "__module__", "") or "")
            visible = callback_module.startswith("ui.")
            captured = StringIO()
            try:
                stream = self.output_stream if visible else captured
                with redirect_stdout(stream):
                    callback(payload)
            except Exception:
                logger.exception(
                    "Fallo procesando evento %s en %s",
                    event_name,
                    getattr(callback, "__qualname__", repr(callback)),
                )
            finally:
                technical_output = captured.getvalue().strip()
                if technical_output:
                    logger.info(
                        "Salida interna de %s: %s",
                        getattr(callback, "__qualname__", repr(callback)),
                        technical_output.replace("\n", " | "),
                    )
