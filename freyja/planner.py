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
    requires_large_pad: bool = False
    allow_planetary: bool = True
    excluded_systems: frozenset[str] = frozenset()
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
    buy_has_large_pad: bool = True
    sell_has_large_pad: bool = True
    buy_planetary: bool = False
    sell_planetary: bool = False

@dataclass(frozen=True, slots=True)
class QuickTradePlan:
    opportunity: MarketOpportunity; units: int; investment: int
    estimated_profit: int; estimated_minutes: float
    profit_per_minute: float; stale_hours: float
    recommended_sale_tons: int

    def sale_instruction(self) -> str:
        unit = "tonelada" if self.recommended_sale_tons == 1 else "toneladas"
        return (
            f"Comandante, vendé {self.recommended_sale_tons} {unit} de "
            f"{self.opportunity.commodity} en {self.opportunity.sell_station} "
            "para conservar la ganancia estimada."
        )

class TradeProfileBuilder:
    LARGE_SHIPS = {
        "anaconda", "belugaliner", "cutter", "federation_corvette",
        "type9", "type9_heavy", "type10", "type10_defender",
    }

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
        ship_type = str(getattr(navigation, "ship_type", "") or "")
        normalized_ship = ship_type.strip("$").removesuffix("_name;").casefold()
        return TradeProfile(
            getattr(navigation,"current_system","") or getattr(commander,"current_system",""),
            credits,reserve,int(getattr(navigation,"cargo_capacity",0) or 0),used,
            float(getattr(navigation,"max_jump_range",0) or 0),
            getattr(navigation,"current_position",None),
            normalized_ship in TradeProfileBuilder.LARGE_SHIPS,
        )

class QuickRouteOptimizer:
    def choose(self, profile: TradeProfile, opportunities, *, max_age_hours=8.0):
        plans=[]
        excluded = {
            system.casefold()
            for system in getattr(profile, "excluded_systems", frozenset())
        }
        for item in opportunities:
            if item.buy_system.casefold() in excluded or item.sell_system.casefold() in excluded:
                continue
            if getattr(profile, "requires_large_pad", False) and not (
                item.buy_has_large_pad and item.sell_has_large_pad
            ):
                continue
            if not getattr(profile, "allow_planetary", True) and (
                item.buy_planetary or item.sell_planetary
            ):
                continue
            age=self._age_hours(item.updated_at)
            if item.buy_price<=0 or item.sell_price<=item.buy_price or age>max_age_hours: continue
            full_price_limit=max(1,math.floor(max(0,item.demand)*0.25))
            units=min(profile.cargo_free,profile.available_capital//item.buy_price,
                      max(0,item.supply),max(0,item.demand),full_price_limit)
            if units<=0 or item.jumps<0: continue
            profit=(item.sell_price-item.buy_price)*units
            minutes=max(1.0, 4.0+item.jumps*1.25+self._supercruise_minutes(item.station_distance_ls))
            plans.append(QuickTradePlan(item,units,item.buy_price*units,profit,minutes,
                                        profit/minutes,age,units))
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
