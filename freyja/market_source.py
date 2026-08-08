"""Fuentes y caché normalizado de mercados para FREYJA."""
from __future__ import annotations
import json
from pathlib import Path
import requests
from core.database import DatabaseManager

class MarketSourceError(RuntimeError): pass

class SpanshMarketClient:
    BASE_URL="https://spansh.co.uk/api"
    def __init__(self, session=None): self.session=session or requests.Session()
    def station(self, market_id: int) -> dict:
        try:
            response=self.session.get(f"{self.BASE_URL}/station/{int(market_id)}",timeout=20)
            response.raise_for_status(); payload=response.json()
        except (requests.RequestException,ValueError,TypeError) as error:
            raise MarketSourceError(f"No se pudo consultar el mercado comunitario: {error}") from error
        record=payload.get("record")
        if not isinstance(record,dict): raise MarketSourceError("Spansh devolvió una estación inválida.")
        return record

class MarketCache:
    def __init__(self,database: DatabaseManager): self.database=database
    def ingest_market_file(self,path: Path) -> int:
        try: payload=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError,TypeError): return 0
        market_id=payload.get("MarketID")
        if market_id is None: return 0
        self._station(market_id,payload.get("StarSystem",""),payload.get("StationName",""),
                      payload.get("timestamp",""),"local")
        count=0
        for item in payload.get("Items",()):
            self._commodity(market_id,item,payload.get("timestamp","")); count+=1
        return count
    def ingest_spansh_station(self,record: dict) -> int:
        market_id=record.get("market_id",record.get("marketId"))
        if market_id is None: return 0
        system=record.get("system_name",record.get("systemName",""))
        station=record.get("name",record.get("station_name",""))
        updated=record.get("updated_at",record.get("updateTime",""))
        self._station(market_id,system,station,updated,"spansh")
        commodities=record.get("market",record.get("commodities",()))
        if isinstance(commodities,dict): commodities=commodities.get("commodities",())
        count=0
        for item in commodities or ():
            self._commodity(market_id,item,updated); count+=1
        return count
    def _station(self,market_id,system,station,updated,source):
        self.database.execute("""INSERT INTO freyja_markets
        (market_id,system_name,station_name,updated_at,source) VALUES(?,?,?,?,?)
        ON CONFLICT(market_id) DO UPDATE SET system_name=excluded.system_name,
        station_name=excluded.station_name,updated_at=excluded.updated_at,source=excluded.source""",
        (int(market_id),system,station,updated,source))
    def _commodity(self,market_id,item,updated):
        name=str(item.get("Name",item.get("name",""))).strip("$").removesuffix("_name;").casefold()
        if not name: return
        self.database.execute("""INSERT INTO freyja_market_commodities
        (market_id,commodity,buy_price,sell_price,mean_price,stock,demand,updated_at)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(market_id,commodity) DO UPDATE SET
        buy_price=excluded.buy_price,sell_price=excluded.sell_price,
        mean_price=excluded.mean_price,stock=excluded.stock,demand=excluded.demand,
        updated_at=excluded.updated_at""",(int(market_id),name,
        int(item.get("BuyPrice",item.get("buy_price",0)) or 0),
        int(item.get("SellPrice",item.get("sell_price",0)) or 0),
        int(item.get("MeanPrice",item.get("mean_price",0)) or 0),
        int(item.get("Stock",item.get("stock",0)) or 0),
        int(item.get("Demand",item.get("demand",0)) or 0),updated))
