"""
ODIN - Orbital Data Intelligence Nexus

event_bus.py

Distribuye eventos externos de Elite Dangerous
y eventos internos generados por ODIN.
"""


class EventBus:
    """
    Centro de comunicaciones de ODIN.
    """

    def __init__(self) -> None:
        self.subscribers: dict[str, list] = {}

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
            callback(payload)