"""Fuentes y caché normalizado de mercados para FREYJA."""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone
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
    def stations_near(
        self, coordinates, *, size: int = 75, page: int = 0,
        sort_by: str = "distance", require_market: bool = True,
    ) -> tuple[dict, ...]:
        x,y,z=coordinates
        payload={
            "filters":({"has_market":{"value":True}} if require_market else {}),
            "sort":[{
                str(sort_by): {
                    "direction": "desc" if sort_by == "market_updated_at" else "asc"
                }
            }],
            "size":max(1,min(int(size),100)),"page":max(0,int(page)),
            "reference_coords":{"x":x,"y":y,"z":z},
        }
        try:
            response=self.session.post(
                f"{self.BASE_URL}/stations/search",json=payload,timeout=25
            )
            response.raise_for_status(); result=response.json()
        except (requests.RequestException,ValueError,TypeError) as error:
            raise MarketSourceError(
                f"No se pudo actualizar la regi\u00f3n comercial: {error}"
            ) from error
        records=result.get("results")
        if not isinstance(records,list):
            raise MarketSourceError("Spansh devolvi\u00f3 una b\u00fasqueda comercial inv\u00e1lida.")
        return tuple(record for record in records if isinstance(record,dict))

    def stations_near_power(
        self, coordinates, power: str, *, size: int = 100, page: int = 0
    ) -> tuple[dict, ...]:
        x,y,z=coordinates
        payload={
            "filters":{
                "has_market":{"value":True},
                "system_controlling_power":{"value":str(power)},
            },
            "sort":[{"distance":{"direction":"asc"}}],
            "size":max(1,min(int(size),100)),"page":max(0,int(page)),
            "reference_coords":{"x":x,"y":y,"z":z},
        }
        try:
            response=self.session.post(
                f"{self.BASE_URL}/stations/search",json=payload,timeout=25
            )
            response.raise_for_status(); result=response.json()
        except (requests.RequestException,ValueError,TypeError) as error:
            raise MarketSourceError(
                f"No se pudo consultar mercados Powerplay: {error}"
            ) from error
        records=result.get("results")
        if not isinstance(records,list):
            raise MarketSourceError("Spansh devolvió una búsqueda Powerplay inválida.")
        return tuple(record for record in records if isinstance(record,dict))

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
    def refresh_region(
        self, client: SpanshMarketClient, coordinates, *, size=75, pages=1,
        sort_by="distance",
    ) -> int:
        stations=tuple(
            station
            for page in range(max(1,int(pages)))
            for station in client.stations_near(
                coordinates, size=size, page=page, sort_by=sort_by
            )
        )
        with self.database.transaction():
            for station in stations: self.ingest_spansh_station(station)
        return len(stations)
    def refresh_stations(self, client: SpanshMarketClient, coordinates, *, pages=3) -> int:
        """Actualiza estaciones con o sin mercado para localizar servicios potenciales."""
        stations=tuple(
            station for page in range(max(1,int(pages)))
            for station in client.stations_near(
                coordinates,size=100,page=page,require_market=False
            )
        )
        with self.database.transaction():
            for station in stations: self.ingest_spansh_station(station)
        return len(stations)
    def opportunities(self,profile,*,sell_power: str = "") -> list[MarketOpportunity]:
        if profile.position is None or profile.jump_range <= 0:
            return []
        power_filter = " AND lower(sm.power_name)=lower(?)" if sell_power else ""
        rows=self.database.query("""SELECT
          buy.commodity, buy.buy_price, buy.stock, buy.updated_at buy_updated,
          sell.sell_price, sell.demand, sell.updated_at sell_updated,
          bm.system_name buy_system,bm.station_name buy_station,
          bm.x bx,bm.y by,bm.z bz,bm.distance_to_arrival buy_ls,
          bm.has_large_pad buy_large,bm.is_planetary buy_planetary,
          sm.system_name sell_system,sm.station_name sell_station,
          sm.x sx,sm.y sy,sm.z sz,sm.distance_to_arrival sell_ls,
          sm.has_large_pad sell_large,sm.is_planetary sell_planetary,
          sm.power_name sell_power,sm.power_state sell_power_state,
          bm.station_type buy_station_type,sm.station_type sell_station_type
          FROM freyja_market_commodities buy
          JOIN freyja_markets bm ON bm.market_id=buy.market_id
          JOIN freyja_market_commodities sell ON sell.commodity=buy.commodity
          JOIN freyja_markets sm ON sm.market_id=sell.market_id
          WHERE buy.market_id<>sell.market_id AND buy.buy_price>0 AND buy.stock>0
          AND sell.sell_price>buy.buy_price AND sell.demand>0
          AND bm.x IS NOT NULL AND sm.x IS NOT NULL""" + power_filter + """
          ORDER BY (
            (sell.sell_price-buy.buy_price)
            * MIN(buy.stock, sell.demand)
          ) DESC
          LIMIT 5000""", (sell_power,) if sell_power else ())
        result=[]
        for row in rows:
            origin=profile.position; buy=(row["bx"],row["by"],row["bz"])
            sell=(row["sx"],row["sy"],row["sz"])
            distance=math.dist(origin,buy)+math.dist(buy,sell)
            jumps=math.ceil(distance/profile.jump_range)
            updated=self._oldest_update(
                row["buy_updated"], row["sell_updated"]
            )
            result.append(MarketOpportunity(
              row["commodity"],row["buy_system"],row["buy_station"],
              row["sell_system"],row["sell_station"],row["buy_price"],row["sell_price"],
              row["stock"],row["demand"],jumps,
              float(row["buy_ls"] or 0)+float(row["sell_ls"] or 0),updated,
              bool(row["buy_large"]),bool(row["sell_large"]),
              bool(row["buy_planetary"]),bool(row["sell_planetary"]),
              str(row["sell_power"] or ""),str(row["sell_power_state"] or ""),
              str(row["buy_station_type"] or ""),str(row["sell_station_type"] or "")))
        return result

    def sales_in_systems(
        self, commodity: str, systems, *, requires_large_pad: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """Lee ventas de la caché existente sin efectuar consultas externas."""

        wanted = " ".join(str(commodity).casefold().split())
        names = tuple(dict.fromkeys(
            " ".join(str(system).split()) for system in systems if str(system).strip()
        ))
        if not wanted or not names:
            return []
        placeholders = ",".join("?" for _ in names)
        pad_filter = " AND m.has_large_pad=1" if requires_large_pad else ""
        rows = self.database.query(f"""SELECT
            m.system_name,m.station_name,m.has_large_pad,m.is_planetary,
            m.distance_to_arrival,m.updated_at,m.power_name,m.power_state,
            c.commodity,c.sell_price,c.demand
            FROM freyja_market_commodities c
            JOIN freyja_markets m ON m.market_id=c.market_id
            WHERE lower(c.commodity)=? AND c.sell_price>0 AND c.demand>0
            AND m.system_name IN ({placeholders}){pad_filter}
            ORDER BY c.sell_price DESC,c.demand DESC
            LIMIT ?""", (wanted, *names, max(1, int(limit))))
        return [dict(row) for row in rows]

    def stations_in_systems(
        self, systems, *, requires_large_pad: bool = False, limit: int = 30,
    ) -> list[dict]:
        """Lista estaciones conocidas; no presupone que tengan contacto Powerplay."""

        names = tuple(dict.fromkeys(
            " ".join(str(system).split()) for system in systems if str(system).strip()
        ))
        if not names:
            return []
        placeholders = ",".join("?" for _ in names)
        pad_filter = " AND has_large_pad=1" if requires_large_pad else ""
        rows = self.database.query(f"""SELECT system_name,station_name,
            has_large_pad,is_planetary,distance_to_arrival,updated_at,
            power_name,power_state,station_type,services_json
            FROM freyja_markets WHERE system_name IN ({placeholders}){pad_filter}
            ORDER BY is_planetary ASC,distance_to_arrival ASC
            LIMIT ?""", (*names, max(1, int(limit))))
        return [dict(row) for row in rows]
    def stations_with_service(
        self, systems, service: str, *, requires_large_pad: bool = False,
        limit: int = 30,
    ) -> list[dict]:
        """Filtra servicios normalizados conservados en la caché comunitaria."""
        wanted=" ".join(str(service).casefold().replace("_"," ").split())
        stations=self.stations_in_systems(
            systems,requires_large_pad=requires_large_pad,limit=max(limit*4,100)
        )
        result=[]
        for station in stations:
            try: services=json.loads(station.get("services_json") or "[]")
            except (TypeError,ValueError): services=[]
            normalized={" ".join(str(item).casefold().replace("_"," ").split()) for item in services}
            if wanted in normalized: result.append(station)
        return result[:max(1,int(limit))]
    def _station(self,market_id,system,station,updated,source,record=None):
        record=record or {}
        self.database.execute("""INSERT INTO freyja_markets
        (market_id,system_name,station_name,updated_at,source,x,y,z,distance_to_arrival,
         has_large_pad,is_planetary,power_name,power_state,station_type,services_json)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(market_id) DO UPDATE SET system_name=excluded.system_name,
        station_name=excluded.station_name,updated_at=excluded.updated_at,source=excluded.source,
        x=COALESCE(excluded.x,freyja_markets.x),
        y=COALESCE(excluded.y,freyja_markets.y),
        z=COALESCE(excluded.z,freyja_markets.z),
        distance_to_arrival=COALESCE(
            excluded.distance_to_arrival,freyja_markets.distance_to_arrival
        ),
        has_large_pad=CASE WHEN excluded.source='local'
            THEN freyja_markets.has_large_pad ELSE excluded.has_large_pad END,
        is_planetary=CASE WHEN excluded.source='local'
            THEN freyja_markets.is_planetary ELSE excluded.is_planetary END,
        power_name=CASE WHEN excluded.source='local'
            THEN freyja_markets.power_name ELSE excluded.power_name END,
        power_state=CASE WHEN excluded.source='local'
            THEN freyja_markets.power_state ELSE excluded.power_state END,
        station_type=CASE WHEN excluded.source='local'
            THEN freyja_markets.station_type ELSE excluded.station_type END,
        services_json=CASE WHEN excluded.source='local'
            THEN freyja_markets.services_json ELSE excluded.services_json END""",
        (int(market_id),system,station,updated,source,record.get("system_x"),
         record.get("system_y"),record.get("system_z"),record.get("distance_to_arrival"),
         int(bool(record.get("has_large_pad"))),int(bool(record.get("is_planetary"))),
         self._power_name(record),self._power_state(record),str(record.get("type","") or ""),
         json.dumps(self._services(record),ensure_ascii=False)))

    @staticmethod
    def _services(record):
        services=record.get("services",record.get("station_services",())) or ()
        if isinstance(services,dict): services=services.get("services",services.keys())
        return sorted({str(item).strip() for item in services if str(item).strip()})

    @staticmethod
    def _oldest_update(*values) -> str:
        parsed = []
        for value in values:
            try:
                stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                parsed.append((stamp.astimezone(timezone.utc), str(value)))
            except (ValueError, TypeError):
                return ""
        return min(parsed, key=lambda item: item[0])[1] if parsed else ""

    @staticmethod
    def _power_name(record):
        power=record.get("system_controlling_power",record.get(
            "power",record.get("controlling_power",record.get("system_power",""))
        ))
        if isinstance(power,dict): return str(power.get("name",power.get("Name","")) or "")
        if isinstance(power,(list,tuple)): return "|".join(str(item) for item in power)
        return str(power or "")

    @staticmethod
    def _power_state(record):
        state=record.get("power_state",record.get("powerplay_state",record.get("system_power_state","")))
        if isinstance(state,dict): return str(state.get("name",state.get("Name","")) or "")
        return str(state or "")
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
