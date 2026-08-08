"""Libro comercial persistente de FREYJA."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from core.database import DatabaseManager

@dataclass(frozen=True, slots=True)
class TradeSummary:
    purchases: int; sales: int; invested: int; revenue: int
    realized_profit: int; cargo_units: int

class TradeLedger:
    EVENTS = {"MarketBuy", "MarketSell", "MiningRefined", "CollectCargo", "EjectCargo"}
    def __init__(self, database: DatabaseManager, diagnostics=None):
        self.database, self.diagnostics = database, diagnostics

    def handle(self, event: dict) -> None:
        kind = str(event.get("event", ""))
        if kind not in self.EVENTS: return
        key = hashlib.sha256(json.dumps(event, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if self.database.query("SELECT 1 FROM freyja_trade_events WHERE event_key=?", (key,)): return
        quantity = int(event.get("Count", 1 if kind in {"MiningRefined","CollectCargo"} else 0))
        if kind == "MarketBuy":
            total = int(event.get("TotalCost", quantity * int(event.get("BuyPrice", 0))))
            self._change(event, quantity, total, "purchased")
            self._record(event, key, quantity, total, 0, True)
        elif kind == "MarketSell": self._sell(event, key, quantity)
        elif kind in {"MiningRefined", "CollectCargo"}:
            self._change(event, quantity, 0, "mined" if kind == "MiningRefined" else "collected")
            self._record(event, key, quantity, 0, 0, True)
        else: self._eject(event, key, quantity)
        if self.diagnostics: self.diagnostics.record_trade_event(event, self.summary())

    def summary(self) -> TradeSummary:
        row = self.database.query("""SELECT
        SUM(CASE WHEN event_type='MarketBuy' THEN quantity ELSE 0 END) purchases,
        SUM(CASE WHEN event_type='MarketSell' THEN quantity ELSE 0 END) sales,
        SUM(CASE WHEN event_type='MarketBuy' THEN total_value ELSE 0 END) invested,
        SUM(CASE WHEN event_type='MarketSell' THEN total_value ELSE 0 END) revenue,
        SUM(realized_profit) profit FROM freyja_trade_events""")[0]
        cargo = self.database.query("SELECT COALESCE(SUM(quantity),0) quantity FROM freyja_inventory")[0]
        values = [int(row[name] or 0) for name in ("purchases","sales","invested","revenue","profit")]
        return TradeSummary(*values, int(cargo["quantity"] or 0))

    def _sell(self, event, key, quantity):
        total = int(event.get("TotalSale", quantity * int(event.get("SellPrice",0))))
        row = self._inventory(self._commodity(event))
        average = int(event.get("AvgPricePaid",0) or 0)
        known = average > 0 or row is not None
        if average <= 0 and row is not None and int(row["quantity"]) > 0:
            average = round(int(row["total_cost"]) / int(row["quantity"]))
        cost = average * quantity
        self._change(event, -quantity, -cost, row["source"] if row else "unknown")
        self._record(event, key, quantity, total, total-cost, known)

    def _eject(self, event, key, quantity):
        row = self._inventory(self._commodity(event))
        average = round(int(row["total_cost"])/int(row["quantity"])) if row and int(row["quantity"]) else 0
        cost = average * quantity
        self._change(event, -quantity, -cost, row["source"] if row else "unknown")
        self._record(event, key, quantity, 0, -cost, row is not None)

    def _change(self, event, quantity_delta, cost_delta, source):
        commodity, row = self._commodity(event), self._inventory(self._commodity(event))
        quantity = max(0, int(row["quantity"] if row else 0)+quantity_delta)
        cost = max(0, int(row["total_cost"] if row else 0)+cost_delta) if quantity else 0
        self.database.execute("""INSERT INTO freyja_inventory
        (commodity,localised_name,quantity,total_cost,source,updated_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(commodity) DO UPDATE SET localised_name=excluded.localised_name,
        quantity=excluded.quantity,total_cost=excluded.total_cost,source=excluded.source,
        updated_at=excluded.updated_at""", (commodity,event.get("Type_Localised",commodity),
        quantity,cost,source,event.get("timestamp","")))

    def _record(self,event,key,quantity,total,profit,known):
        self.database.execute("""INSERT INTO freyja_trade_events
        (event_key,timestamp,event_type,market_id,commodity,localised_name,quantity,
        unit_price,total_value,realized_profit,cost_known,raw_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (key,event.get("timestamp",""),event.get("event",""),event.get("MarketID"),
        self._commodity(event),event.get("Type_Localised",""),quantity,
        int(event.get("BuyPrice",event.get("SellPrice",0)) or 0),total,profit,int(known),
        json.dumps(event,ensure_ascii=False)))

    def _inventory(self, commodity):
        rows=self.database.query("SELECT * FROM freyja_inventory WHERE commodity=?",(commodity,))
        return rows[0] if rows else None
    @staticmethod
    def _commodity(event):
        return str(event.get("Type","unknown")).strip("$").removesuffix("_name;").casefold()
