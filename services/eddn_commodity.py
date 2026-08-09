"""Normalizacion local de Market.json para commodity/3 de EDDN."""

from __future__ import annotations


class EDDNCommodityMessageBuilder:
    SCHEMA_REF = "https://eddn.edcd.io/schemas/commodity/3"
    REQUIRED_ITEM_FIELDS = (
        ("meanPrice", "MeanPrice"), ("buyPrice", "BuyPrice"),
        ("stock", "Stock"), ("stockBracket", "StockBracket"),
        ("sellPrice", "SellPrice"), ("demand", "Demand"),
        ("demandBracket", "DemandBracket"),
    )

    def __init__(self, journal_builder) -> None:
        self.journal_builder = journal_builder

    def prepare(self, market_event: dict, payload: dict) -> dict | None:
        if market_event.get("event") != "Market" or not isinstance(payload, dict):
            return None
        if not self._same_market(market_event, payload):
            return None
        items = payload.get("Items")
        if not isinstance(items, list):
            return None
        commodities = []
        for item in items:
            normalized = self._commodity(item)
            if normalized is not None:
                commodities.append(normalized)
        message = {
            "systemName": str(payload.get("StarSystem", "") or ""),
            "stationName": str(payload.get("StationName", "") or ""),
            "marketId": payload.get("MarketID"),
            "timestamp": payload.get("timestamp"),
            "commodities": commodities,
        }
        if not (
            message["systemName"] and message["stationName"]
            and isinstance(message["marketId"], int)
            and not isinstance(message["marketId"], bool)
            and message["timestamp"] and commodities
        ):
            return None
        if self.journal_builder.horizons is not None:
            message["horizons"] = self.journal_builder.horizons
        if self.journal_builder.odyssey is not None:
            message["odyssey"] = self.journal_builder.odyssey
        header = {
            "uploaderID": self.journal_builder.uploader_id,
            "softwareName": self.journal_builder.software_name,
            "softwareVersion": self.journal_builder.software_version,
            "gameversion": self.journal_builder.gameversion,
            "gamebuild": self.journal_builder.gamebuild,
        }
        schema = self.SCHEMA_REF + (
            "/test" if self.journal_builder.test_mode else ""
        )
        return {"$schemaRef": schema, "header": header, "message": message}

    @classmethod
    def _commodity(cls, item) -> dict | None:
        if not isinstance(item, dict):
            return None
        category = str(item.get("Category", item.get("categoryname", "")) or "")
        legality = str(item.get("Legality", item.get("legality", "")) or "")
        if "nonmarketable" in category.casefold() or legality.strip():
            return None
        name = str(item.get("Name", item.get("name", "")) or "")
        name = name.strip("$").removesuffix("_name;")
        if not name:
            return None
        result = {"name": name}
        for target, source in cls.REQUIRED_ITEM_FIELDS:
            value = item.get(source, item.get(target))
            if not isinstance(value, int) or isinstance(value, bool):
                return None
            result[target] = value
        flags = [
            flag for flag in ("Producer", "Consumer", "Rare")
            if item.get(flag) is True
        ]
        if flags:
            result["statusFlags"] = flags
        return result

    @staticmethod
    def _same_market(event: dict, payload: dict) -> bool:
        comparisons = (
            ("MarketID", lambda value: value),
            ("StarSystem", lambda value: str(value).casefold()),
            ("StationName", lambda value: str(value).casefold()),
        )
        for key, normalize in comparisons:
            if key not in event or key not in payload:
                return False
            if normalize(event[key]) != normalize(payload[key]):
                return False
        return True
