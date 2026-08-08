"""Fuentes y caché normalizado de mercados para FREYJA."""
from __future__ import annotations
import json
import math
from pathlib import Path
import requests
from core.database import DatabaseManager
from freyja.planner import MarketOpportunity

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
        updated=record.get("market_updated_at",record.get("updated_at",record.get("updateTime","")))
        self._station(market_id,system,station,updated,"spansh",record)
        commodities=record.get("market",record.get("commodities",()))
        if isinstance(commodities,dict): commodities=commodities.get("commodities",())
        count=0
        for item in commodities or ():
            self._commodity(market_id,item,updated); count+=1
        return count
    def opportunities(self,profile) -> list[MarketOpportunity]:
        if profile.position is None or profile.jump_range <= 0:
            return []
        rows=self.database.query("""SELECT
          buy.commodity, buy.buy_price, buy.stock, buy.updated_at buy_updated,
          sell.sell_price, sell.demand, sell.updated_at sell_updated,
          bm.system_name buy_system,bm.station_name buy_station,
          bm.x bx,bm.y by,bm.z bz,bm.distance_to_arrival buy_ls,
          bm.has_large_pad buy_large,bm.is_planetary buy_planetary,
          sm.system_name sell_system,sm.station_name sell_station,
          sm.x sx,sm.y sy,sm.z sz,sm.distance_to_arrival sell_ls,
          sm.has_large_pad sell_large,sm.is_planetary sell_planetary
          FROM freyja_market_commodities buy
          JOIN freyja_markets bm ON bm.market_id=buy.market_id
          JOIN freyja_market_commodities sell ON sell.commodity=buy.commodity
          JOIN freyja_markets sm ON sm.market_id=sell.market_id
          WHERE buy.market_id<>sell.market_id AND buy.buy_price>0 AND buy.stock>0
          AND sell.sell_price>buy.buy_price AND sell.demand>0
          AND bm.x IS NOT NULL AND sm.x IS NOT NULL""")
        result=[]
        for row in rows:
            origin=profile.position; buy=(row["bx"],row["by"],row["bz"])
            sell=(row["sx"],row["sy"],row["sz"])
            distance=math.dist(origin,buy)+math.dist(buy,sell)
            jumps=math.ceil(distance/profile.jump_range)
            updated=min(str(row["buy_updated"]),str(row["sell_updated"]))
            result.append(MarketOpportunity(
              row["commodity"],row["buy_system"],row["buy_station"],
              row["sell_system"],row["sell_station"],row["buy_price"],row["sell_price"],
              row["stock"],row["demand"],jumps,
              float(row["buy_ls"] or 0)+float(row["sell_ls"] or 0),updated,
              bool(row["buy_large"]),bool(row["sell_large"]),
              bool(row["buy_planetary"]),bool(row["sell_planetary"])))
        return result
    def _station(self,market_id,system,station,updated,source,record=None):
        record=record or {}
        self.database.execute("""INSERT INTO freyja_markets
        (market_id,system_name,station_name,updated_at,source,x,y,z,distance_to_arrival,
         has_large_pad,is_planetary) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(market_id) DO UPDATE SET system_name=excluded.system_name,
        station_name=excluded.station_name,updated_at=excluded.updated_at,source=excluded.source,
        x=excluded.x,y=excluded.y,z=excluded.z,distance_to_arrival=excluded.distance_to_arrival,
        has_large_pad=excluded.has_large_pad,is_planetary=excluded.is_planetary""",
        (int(market_id),system,station,updated,source,record.get("system_x"),
         record.get("system_y"),record.get("system_z"),record.get("distance_to_arrival"),
         int(bool(record.get("has_large_pad"))),int(bool(record.get("is_planetary")))))
    def _commodity(self,market_id,item,updated):
        name=str(item.get("Name",item.get("name",item.get("commodity","")))).strip("$").removesuffix("_name;").casefold()
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
        int(item.get("Stock",item.get("stock",item.get("supply",0))) or 0),
        int(item.get("Demand",item.get("demand",0)) or 0),updated))
