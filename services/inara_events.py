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

    def __init__(self) -> None:
        self.current_system = ""
        self.current_station = ""

    def map(self, journal_event: dict) -> tuple[dict, ...]:
        if not isinstance(journal_event, dict):
            return ()
        timestamp = journal_event.get("timestamp")
        if not timestamp:
            return ()
        kind = journal_event.get("event")
        self.remember_location(journal_event)
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
        if kind == "Cargo":
            return self._cargo(journal_event, timestamp)
        if kind == "Materials":
            return self._materials(journal_event, timestamp)
        if kind in {"Touchdown", "DropShipDeploy"}:
            return self._land(journal_event, timestamp)
        if kind == "CarrierJump":
            return self._carrier_jump(journal_event, timestamp)
        if kind in {
            "Powerplay", "PowerplayRank", "PowerplayMerits",
            "PowerplayJoin", "PowerplayLeave", "PowerplayDefect",
        }:
            return self._powerplay(journal_event, timestamp)
        if kind == "Reputation":
            return self._major_reputation(journal_event, timestamp)
        if kind == "MissionAccepted":
            return self._mission_accepted(journal_event, timestamp)
        if kind in {"MissionCompleted", "MissionAbandoned", "MissionFailed"}:
            return self._mission_status(journal_event, timestamp)
        return ()

    def remember_location(self, event: dict) -> None:
        kind = event.get("event")
        if kind in {"FSDJump", "CarrierJump"} and event.get("StarSystem"):
            self.current_system = str(event["StarSystem"])
            self.current_station = ""
        elif kind == "Docked" and event.get("StarSystem") and event.get("StationName"):
            self.current_system = str(event["StarSystem"])
            self.current_station = str(event["StationName"])
        elif kind == "Location" and event.get("StarSystem"):
            self.current_system = str(event["StarSystem"])
            self.current_station = str(event.get("StationName", "")) if event.get("Docked") else ""

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
        events = [self._event("addCommanderTravelFSDJump", timestamp, data)]
        events.extend(self._minor_reputation(event, timestamp))
        return tuple(events)

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
        events = [self._event("setCommanderTravelLocation", timestamp, data)]
        events.extend(self._minor_reputation(event, timestamp))
        return tuple(events)

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
        events = [self._event("setCommanderShip", timestamp, data)]
        if event.get("event") == "Loadout":
            modules = self._ship_modules(event.get("Modules"))
            if modules:
                events.append(self._event(
                    "setCommanderShipLoadout", timestamp,
                    {
                        "shipType": str(ship_type),
                        "shipGameID": ship_id,
                        "shipLoadout": modules,
                    },
                ))
        return tuple(events)

    def _ship_modules(self, modules) -> list[dict]:
        if not isinstance(modules, list):
            return []
        translated = []
        for module in modules:
            if not isinstance(module, dict) or not module.get("Slot") or not module.get("Item"):
                continue
            data = {
                "slotName": str(module["Slot"]),
                "itemName": str(module["Item"]),
            }
            for target, source, expected in (
                ("itemValue", "Value", (int, float)),
                ("itemHealth", "Health", (int, float)),
                ("isOn", "On", bool),
                ("isHot", "Hot", bool),
                ("itemPriority", "Priority", int),
                ("itemAmmoClip", "AmmoInClip", int),
                ("itemAmmoHopper", "AmmoInHopper", int),
            ):
                self._optional(data, target, module.get(source), expected)
            engineering = self._engineering(module.get("Engineering"))
            if engineering:
                data["engineering"] = engineering
            translated.append(data)
        return translated

    def _engineering(self, engineering) -> dict:
        if not isinstance(engineering, dict):
            return {}
        data = {}
        for target, source, expected in (
            ("blueprintName", "BlueprintName", str),
            ("blueprintLevel", "Level", int),
            ("blueprintQuality", "Quality", (int, float)),
            ("experimentalEffect", "ExperimentalEffect", str),
        ):
            self._optional(data, target, engineering.get(source), expected)
        modifiers = []
        raw_modifiers = engineering.get("Modifiers", [])
        if not isinstance(raw_modifiers, list):
            raw_modifiers = []
        for modifier in raw_modifiers:
            if not isinstance(modifier, dict) or not modifier.get("Label"):
                continue
            translated = {"name": str(modifier["Label"])}
            for target, source, expected in (
                ("value", "Value", (int, float)),
                ("originalValue", "OriginalValue", (int, float)),
                ("lessIsGood", "LessIsGood", bool),
            ):
                self._optional(translated, target, modifier.get(source), expected)
            modifiers.append(translated)
        if modifiers:
            data["modifiers"] = modifiers
        return data

    def _cargo(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        inventory = event.get("Inventory")
        if not isinstance(inventory, list):
            return ()
        translated = []
        for item in inventory:
            if not isinstance(item, dict) or not item.get("Name"):
                continue
            count = item.get("Count")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                continue
            stolen = item.get("Stolen", 0)
            stolen = stolen if isinstance(stolen, int) and not isinstance(stolen, bool) else 0
            stolen = max(0, min(stolen, count))
            mission_id = item.get("MissionID")
            common = {}
            if isinstance(mission_id, int) and not isinstance(mission_id, bool):
                common["missionGameID"] = mission_id
            legal_count = count - stolen
            if legal_count:
                translated.append({
                    "itemName": str(item["Name"]), "itemCount": legal_count, **common
                })
            if stolen:
                translated.append({
                    "itemName": str(item["Name"]), "itemCount": stolen,
                    "isStolen": True, **common,
                })
        return (self._event("setCommanderInventoryCargo", timestamp, translated),)

    def _materials(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        categories = [event.get(name) for name in ("Raw", "Manufactured", "Encoded")]
        if not all(isinstance(category, list) for category in categories):
            return ()
        translated = []
        for category in categories:
            for item in category:
                if not isinstance(item, dict) or not item.get("Name"):
                    continue
                count = item.get("Count")
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    continue
                translated.append({"itemName": str(item["Name"]), "itemCount": count})
        return (self._event("setCommanderInventoryMaterials", timestamp, translated),)

    def _land(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        system = event.get("StarSystem")
        body = event.get("Body") or event.get("BodyName")
        if not system or not body:
            return ()
        data = {
            "starsystemName": str(system),
            "starsystemBodyName": str(body),
        }
        self._optional(data, "starsystemCoords", event.get("StarPos"), (list, tuple))
        if isinstance(event.get("Latitude"), (int, float)) and isinstance(
            event.get("Longitude"), (int, float)
        ):
            data["starsystemBodyCoords"] = [
                float(event["Latitude"]), float(event["Longitude"])
            ]
        self._travel_mode(data, event)
        if event.get("event") == "DropShipDeploy":
            data["isTaxiDropship"] = True
        return (self._event("addCommanderTravelLand", timestamp, data),)

    def _carrier_jump(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        system = event.get("StarSystem")
        if not system:
            return ()
        data = {"starsystemName": str(system)}
        self._optional(data, "starsystemCoords", event.get("StarPos"), (list, tuple))
        self._optional(data, "stationName", event.get("StationName"), str)
        self._optional(data, "marketID", event.get("MarketID"), int)
        return (self._event("addCommanderTravelCarrierJump", timestamp, data),)

    def _powerplay(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        power = event.get("Power")
        if not power:
            return ()
        data = {"powerName": str(power)}
        kind = event.get("event")
        rank = event.get("Rank")
        merits = event.get("Merits")
        if kind == "PowerplayMerits":
            merits = event.get("TotalMerits")
        if kind == "PowerplayLeave":
            rank = -1
        elif kind in {"PowerplayJoin", "PowerplayDefect"} and not isinstance(rank, int):
            rank = 0
        if isinstance(rank, int) and not isinstance(rank, bool):
            data["rankValue"] = rank
        if isinstance(merits, int) and not isinstance(merits, bool):
            data["meritsValue"] = max(0, merits)
        if len(data) == 1:
            return ()
        return (self._event("setCommanderRankPower", timestamp, data),)

    def _major_reputation(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        reputations = []
        for journal_name in ("Alliance", "Empire", "Federation", "Independent"):
            value = event.get(journal_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            reputations.append({
                "majorfactionName": journal_name.casefold(),
                "majorfactionReputation": self._reputation(value),
            })
        if not reputations:
            return ()
        return (self._event(
            "setCommanderReputationMajorFaction", timestamp, reputations
        ),)

    def _minor_reputation(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        factions = event.get("Factions")
        if not isinstance(factions, list):
            return ()
        reputations = []
        for faction in factions:
            if not isinstance(faction, dict) or not faction.get("Name"):
                continue
            value = faction.get("MyReputation")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            reputations.append({
                "minorfactionName": str(faction["Name"]),
                "minorfactionReputation": self._reputation(value),
            })
        if not reputations:
            return ()
        return (self._event(
            "setCommanderReputationMinorFaction", timestamp, reputations
        ),)

    def _mission_accepted(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        name, mission_id = event.get("Name"), event.get("MissionID")
        if not name or not isinstance(mission_id, int) or isinstance(mission_id, bool):
            return ()
        data = {"missionName": str(name), "missionGameID": mission_id}
        for target, source, expected in (
            ("missionExpiry", "Expiry", str),
            ("influenceGain", "Influence", str),
            ("reputationGain", "Reputation", str),
            ("minorfactionNameOrigin", "Faction", str),
            ("starsystemNameTarget", "DestinationSystem", str),
            ("stationNameTarget", "DestinationStation", str),
            ("minorfactionNameTarget", "TargetFaction", str),
            ("commodityName", "Commodity", str),
            ("commodityCount", "Count", int),
            ("targetName", "Target", str),
            ("targetType", "TargetType", str),
            ("killCount", "KillCount", int),
            ("passengerType", "PassengerType", str),
            ("passengerCount", "PassengerCount", int),
            ("passengerIsVIP", "PassengerVIPs", bool),
            ("passengerIsWanted", "PassengerWanted", bool),
        ):
            self._optional(data, target, event.get(source), expected)
        if self.current_system:
            data["starsystemNameOrigin"] = self.current_system
        if self.current_station:
            data["stationNameOrigin"] = self.current_station
        return (self._event("addCommanderMission", timestamp, data),)

    def _mission_status(self, event: dict, timestamp: str) -> tuple[dict, ...]:
        mission_id = event.get("MissionID")
        if not isinstance(mission_id, int) or isinstance(mission_id, bool):
            return ()
        kind = event.get("event")
        names = {
            "MissionCompleted": "setCommanderMissionCompleted",
            "MissionAbandoned": "setCommanderMissionAbandoned",
            "MissionFailed": "setCommanderMissionFailed",
        }
        data = {"missionGameID": mission_id}
        if kind == "MissionCompleted":
            donation = event.get("Donation", event.get("Donated"))
            self._optional(data, "donationCredits", donation, int)
            self._optional(data, "rewardCredits", event.get("Reward"), int)
            materials = self._reward_items(event.get("MaterialsReward"))
            if materials:
                data["rewardMaterials"] = materials
            commodities = self._reward_items(event.get("CommodityReward"))
            if commodities:
                data["rewardCommodities"] = commodities
        return (self._event(names[kind], timestamp, data),)

    @staticmethod
    def _reward_items(items) -> list[dict]:
        if not isinstance(items, list):
            return []
        rewards = []
        for item in items:
            if not isinstance(item, dict) or not item.get("Name"):
                continue
            count = item.get("Count")
            if isinstance(count, int) and not isinstance(count, bool) and count > 0:
                rewards.append({"itemName": str(item["Name"]), "itemCount": count})
        return rewards

    @staticmethod
    def _reputation(value: int | float) -> float:
        return max(-1.0, min(float(value) / 100.0, 1.0))

    @staticmethod
    def _optional(data: dict, key: str, value, expected) -> None:
        boolean_expected = expected is bool
        if isinstance(value, expected) and (boolean_expected or not isinstance(value, bool)):
            data[key] = list(value) if isinstance(value, tuple) else value

    @staticmethod
    def _travel_mode(data: dict, event: dict) -> None:
        if event.get("Taxi") is True:
            data["isTaxiShuttle"] = True
