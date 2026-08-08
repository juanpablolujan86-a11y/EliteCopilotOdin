"""Perfil comercial y optimizador inicial de rutas rápidas."""
from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

@dataclass(frozen=True, slots=True)
class TradeProfile:
    system: str; credits: int; reserve_credits: int
    cargo_capacity: int; cargo_used: int; jump_range: float
    position: tuple[float,float,float] | None = None
    @property
    def cargo_free(self): return max(0, self.cargo_capacity-self.cargo_used)
    @property
    def available_capital(self): return max(0, self.credits-self.reserve_credits)

@dataclass(frozen=True, slots=True)
class MarketOpportunity:
    commodity: str; buy_system: str; buy_station: str
    sell_system: str; sell_station: str; buy_price: int; sell_price: int
    supply: int; demand: int; jumps: int; station_distance_ls: float
    updated_at: str

@dataclass(frozen=True, slots=True)
class QuickTradePlan:
    opportunity: MarketOpportunity; units: int; investment: int
    estimated_profit: int; estimated_minutes: float
    profit_per_minute: float; stale_hours: float

class TradeProfileBuilder:
    @staticmethod
    def build(commander, navigation, cargo_file: Path) -> TradeProfile:
        used = 0
        try:
            payload=json.loads(cargo_file.read_text(encoding="utf-8"))
            if payload.get("Vessel") == "Ship": used=int(payload.get("Count",0) or 0)
        except (OSError,ValueError,TypeError): pass
        credits=int(getattr(commander,"credits",0) or 0)
        rebuy=int(getattr(navigation,"rebuy_cost",0) or 0)
        reserve=max(rebuy*2, round(credits*0.05))
        return TradeProfile(
            getattr(navigation,"current_system","") or getattr(commander,"current_system",""),
            credits,reserve,int(getattr(navigation,"cargo_capacity",0) or 0),used,
            float(getattr(navigation,"max_jump_range",0) or 0),
            getattr(navigation,"current_position",None))

class QuickRouteOptimizer:
    def choose(self, profile: TradeProfile, opportunities, *, max_age_hours=8.0):
        plans=[]
        for item in opportunities:
            age=self._age_hours(item.updated_at)
            if item.buy_price<=0 or item.sell_price<=item.buy_price or age>max_age_hours: continue
            units=min(profile.cargo_free,profile.available_capital//item.buy_price,
                      max(0,item.supply),max(0,item.demand))
            if units<=0 or item.jumps<0: continue
            profit=(item.sell_price-item.buy_price)*units
            minutes=max(1.0, 4.0+item.jumps*1.25+self._supercruise_minutes(item.station_distance_ls))
            plans.append(QuickTradePlan(item,units,item.buy_price*units,profit,minutes,
                                        profit/minutes,age))
        return max(plans,key=lambda plan:plan.profit_per_minute,default=None)

    @staticmethod
    def _supercruise_minutes(distance_ls):
        return min(20.0, 0.8+math.sqrt(max(0.0,distance_ls))/18.0)
    @staticmethod
    def _age_hours(value):
        try:
            stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
            return max(0.0,(datetime.now(timezone.utc)-stamp).total_seconds()/3600)
        except (ValueError,TypeError): return math.inf
