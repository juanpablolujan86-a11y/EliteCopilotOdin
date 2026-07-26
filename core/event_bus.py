class EventBus:
    """
    Centro de comunicaciones de ODIN.

    Los módulos pueden suscribirse a eventos y serán notificados
    cuando ocurra uno.
    """

    def __init__(self):
        # Diccionario de suscriptores
        self._subscribers = {}

    def subscribe(self, event_name, callback):
        """
        Registra una función para un tipo de evento.

        Ejemplo:
            bus.subscribe("FSDJump", mi_funcion)
        """

        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        self._subscribers[event_name].append(callback)

    def publish(self, event_name, data):
        """
        Envía un evento a todos los suscriptores.
        """

        if event_name not in self._subscribers:
            return

        for callback in self._subscribers[event_name]:
            callback(data)