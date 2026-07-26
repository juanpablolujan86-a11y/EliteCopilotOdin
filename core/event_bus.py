class EventBus:

    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_name, callback):

        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        self.subscribers[event_name].append(callback)

    def publish(self, event):

        event_name = event.get("event")

        if event_name not in self.subscribers:
            return

        for callback in self.subscribers[event_name]:
            callback(event)