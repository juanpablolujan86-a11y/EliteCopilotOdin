"""Preparacion segura de eventos Journal para el esquema oficial de EDDN."""

from __future__ import annotations

from copy import deepcopy


class EDDNJournalMessageBuilder:
    """Normaliza eventos localmente; esta clase no realiza conexiones de red."""

    SCHEMA_REF = "https://eddn.edcd.io/schemas/journal/1"
    SUPPORTED_EVENTS = frozenset({
        "Docked", "FSDJump", "Scan", "Location", "SAASignalsFound",
        "CarrierJump", "CodexEntry",
    })
    DISALLOWED_FIELDS = frozenset({
        "ActiveFine", "CockpitBreach", "BoostUsed", "FuelLevel", "FuelUsed",
        "JumpDist", "Latitude", "Longitude", "Wanted", "IsNewEntry",
        "NewTraitsDiscovered", "Traits", "VoucherAmount", "HappiestSystem",
        "HomeSystem", "MyReputation", "SquadronFaction",
    })

    def __init__(
        self, uploader_id: str, software_version: str, software_name: str = "ODIN"
    ) -> None:
        self.uploader_id = str(uploader_id).strip()
        self.software_version = str(software_version).strip()
        self.software_name = str(software_name).strip() or "ODIN"
        self.gameversion = ""
        self.gamebuild = ""
        self.horizons: bool | None = None
        self.odyssey: bool | None = None
        self.system_context: dict = {}

    def prepare(self, event: dict) -> dict | None:
        """Devuelve un sobre valido o ``None`` si faltan datos obligatorios."""

        kind = str(event.get("event", "") or "")
        if kind in {"Fileheader", "LoadGame"}:
            self._remember_game_version(event)
            return None
        if kind not in self.SUPPORTED_EVENTS:
            return None

        message = self._sanitize(deepcopy(event))
        location_event = kind in {"FSDJump", "Location", "CarrierJump"}
        if not location_event and not self._matches_system_context(message):
            return None
        for key in ("StarSystem", "StarPos", "SystemAddress"):
            if key not in message and key in self.system_context:
                message[key] = deepcopy(self.system_context[key])
        if self.horizons is not None:
            message["horizons"] = self.horizons
        if self.odyssey is not None:
            message["odyssey"] = self.odyssey
        if not self._valid_message(message):
            return None
        if kind in {"FSDJump", "Location", "CarrierJump"}:
            self.system_context = {
                key: deepcopy(message[key])
                for key in ("StarSystem", "StarPos", "SystemAddress")
            }

        header = {
            "uploaderID": self.uploader_id,
            "softwareName": self.software_name,
            "softwareVersion": self.software_version,
            "gameversion": self.gameversion,
            "gamebuild": self.gamebuild,
        }
        return {"$schemaRef": self.SCHEMA_REF, "header": header, "message": message}

    def _remember_game_version(self, event: dict) -> None:
        self.gameversion = str(
            event.get("gameversion", event.get("GameVersion", self.gameversion)) or ""
        )
        self.gamebuild = str(
            event.get("build", event.get("GameBuild", self.gamebuild)) or ""
        )
        if event.get("event") == "LoadGame":
            if isinstance(event.get("Horizons"), bool):
                self.horizons = event["Horizons"]
            if isinstance(event.get("Odyssey"), bool):
                self.odyssey = event["Odyssey"]

    def _matches_system_context(self, message: dict) -> bool:
        if not self.system_context:
            return True
        for key in ("StarSystem", "SystemAddress", "StarPos"):
            if key not in message:
                continue
            current = self.system_context.get(key)
            if key == "StarSystem":
                if str(message[key]).casefold() != str(current).casefold():
                    return False
            elif message[key] != current:
                return False
        return True

    @classmethod
    def _sanitize(cls, value):
        if isinstance(value, dict):
            return {
                key: cls._sanitize(item)
                for key, item in value.items()
                if not key.endswith("_Localised")
                and key not in cls.DISALLOWED_FIELDS
            }
        if isinstance(value, list):
            return [cls._sanitize(item) for item in value]
        return value

    def _valid_message(self, message: dict) -> bool:
        position = message.get("StarPos")
        address = message.get("SystemAddress")
        return bool(
            self.uploader_id
            and self.software_version
            and message.get("timestamp")
            and message.get("event") in self.SUPPORTED_EVENTS
            and str(message.get("StarSystem", "")).strip()
            and isinstance(position, list)
            and len(position) == 3
            and all(isinstance(value, (int, float)) for value in position)
            and isinstance(address, int)
            and not isinstance(address, bool)
        )
