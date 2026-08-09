"""Traducción conservadora de eventos Journal a eventos de la API de Inara."""

from __future__ import annotations


class InaraEventMapper:
    RANK_NAMES = {
        "Combat": "combat",
        "Trade": "trade",
        "Explore": "explore",
        "CQC": "cqc",
        "Soldier": "soldier",
        "Exobiologist": "exobiologist",
        "Federation": "federation",
        "Empire": "empire",
    }

    def map(self, journal_event: dict) -> tuple[dict, ...]:
        if not isinstance(journal_event, dict):
            return ()
        timestamp = journal_event.get("timestamp")
        if not timestamp:
            return ()
        kind = journal_event.get("event")
        if kind == "LoadGame":
            return self._credits(journal_event, timestamp)
        if kind == "Statistics":
            return self._statistics(journal_event, timestamp)
        if kind == "Rank":
            return self._ranks(journal_event, timestamp, "rankValue", float_values=False)
        if kind == "Progress":
            return self._ranks(journal_event, timestamp, "rankProgress", float_values=True)
        return ()

    @staticmethod
    def _event(name: str, timestamp: str, data) -> dict:
        return {
            "eventName": name,
            "eventTimestamp": str(timestamp),
            "eventData": data,
        }

    def _credits(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        credits = event.get("Credits")
        if not isinstance(credits, (int, float)) or isinstance(credits, bool):
            return ()
        data = {
            "commanderCredits": int(credits),
            "commanderLoan": int(event.get("Loan", 0) or 0),
        }
        return (self._event("setCommanderCredits", timestamp, data),)

    def _statistics(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        data = {
            key: value for key, value in event.items()
            if key not in {"timestamp", "event"}
        }
        if not data:
            return ()
        return (self._event("setCommanderGameStatistics", timestamp, data),)

    def _ranks(
        self, event: dict, timestamp: str, value_name: str,
        *, float_values: bool,
    ) -> tuple[dict, ...]:
        ranks = []
        for journal_name, inara_name in self.RANK_NAMES.items():
            value = event.get(journal_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            if float_values:
                value = max(0.0, min(float(value) / 100.0, 1.0))
            else:
                value = int(value)
            ranks.append({"rankName": inara_name, value_name: value})
        if not ranks:
            return ()
        return (self._event("setCommanderRankPilot", timestamp, ranks),)
