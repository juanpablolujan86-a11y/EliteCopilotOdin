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
        if kind == "FSDJump":
            return self._fsd_jump(journal_event, timestamp)
        if kind == "Docked":
            return self._docked(journal_event, timestamp)
        if kind == "Location":
            return self._location(journal_event, timestamp)
        if kind in {"Loadout", "SetUserShipName"}:
            return self._ship(journal_event, timestamp)
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

    def _fsd_jump(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        system = event.get("StarSystem")
        if not system:
            return ()
        data = {"starsystemName": str(system)}
        self._optional(data, "starsystemCoords", event.get("StarPos"), (list, tuple))
        self._optional(data, "jumpDistance", event.get("JumpDist"), (int, float))
        self._travel_mode(data, event)
        return (self._event("addCommanderTravelFSDJump", timestamp, data),)

    def _docked(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        system, station = event.get("StarSystem"), event.get("StationName")
        if not system or not station:
            return ()
        data = {"starsystemName": str(system), "stationName": str(station)}
        self._optional(data, "marketID", event.get("MarketID"), int)
        self._travel_mode(data, event)
        return (self._event("addCommanderTravelDock", timestamp, data),)

    def _location(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        system = event.get("StarSystem")
        if not system:
            return ()
        data = {"starsystemName": str(system)}
        self._optional(data, "starsystemCoords", event.get("StarPos"), (list, tuple))
        if event.get("Docked"):
            self._optional(data, "stationName", event.get("StationName"), str)
            self._optional(data, "marketID", event.get("MarketID"), int)
        self._optional(data, "starsystemBodyName", event.get("Body"), str)
        if isinstance(event.get("Latitude"), (int, float)) and isinstance(
            event.get("Longitude"), (int, float)
        ):
            data["starsystemBodyCoords"] = [
                float(event["Latitude"]), float(event["Longitude"])
            ]
        return (self._event("setCommanderTravelLocation", timestamp, data),)

    def _ship(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        ship_type, ship_id = event.get("Ship"), event.get("ShipID")
        if not ship_type or not isinstance(ship_id, int):
            return ()
        data = {
            "shipType": str(ship_type),
            "shipGameID": ship_id,
            "isCurrentShip": True,
        }
        for target, source in (
            ("shipName", "ShipName"), ("shipIdent", "ShipIdent"),
            ("shipName", "UserShipName"), ("shipIdent", "UserShipId"),
        ):
            self._optional(data, target, event.get(source), str)
        for target, source, expected in (
            ("shipHullValue", "HullValue", (int, float)),
            ("shipModulesValue", "ModulesValue", (int, float)),
            ("shipRebuyCost", "Rebuy", (int, float)),
            ("shipMaxJumpRange", "MaxJumpRange", (int, float)),
            ("shipCargoCapacity", "CargoCapacity", (int, float)),
        ):
            self._optional(data, target, event.get(source), expected)
        return (self._event("setCommanderShip", timestamp, data),)

    @staticmethod
    def _optional(data: dict, key: str, value, expected) -> None:
        if isinstance(value, expected) and not isinstance(value, bool):
            data[key] = list(value) if isinstance(value, tuple) else value

    @staticmethod
    def _travel_mode(data: dict, event: dict) -> None:
        if event.get("Taxi") is True:
            data["isTaxiShuttle"] = True
