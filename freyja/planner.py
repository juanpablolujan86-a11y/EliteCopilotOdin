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
    estimated_bulk_discount: float
    estimated_sell_price: int
    cargo_utilization: float

    def sale_instruction(self) -> str:
        unit = "tonelada" if self.recommended_sale_tons == 1 else "toneladas"
        instruction = (
            f"Comandante, vendé {self.recommended_sale_tons} {unit} de "
            f"{self.opportunity.commodity} en {self.opportunity.sell_station}. "
        )
        if self.estimated_bulk_discount > 0:
            return instruction + (
                "La reducción estimada por volumen es de "
                f"{self.estimated_bulk_discount * 100:.1f} por ciento, "
                "dentro del límite aceptado."
            )
        return instruction + "No se estima penalización por volumen."


@dataclass(frozen=True, slots=True)
class ThreeStationTradePlan:
    legs: tuple[QuickTradePlan, QuickTradePlan, QuickTradePlan]
    estimated_profit: int
    estimated_minutes: float
    profit_per_minute: float
    total_jumps: int

    def summary(self) -> str:
        stations = [self.legs[0].opportunity.buy_station]
        stations.extend(leg.opportunity.sell_station for leg in self.legs)
        return (
            " → ".join(stations)
            + f": {self.estimated_profit:,} créditos estimados en "
            f"{self.total_jumps} saltos."
        )


@dataclass(frozen=True, slots=True)
class TradeExpeditionPlan:
    legs: tuple[QuickTradePlan, ...]
    estimated_profit: int
    estimated_minutes: float
    profit_per_minute: float
    total_jumps: int

    def summary(self) -> str:
        return (
            f"Expedición de {len(self.legs)} operaciones y {self.total_jumps} "
            f"saltos: {self.estimated_profit:,} créditos estimados."
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
    BULK_FULL_PRICE_RATIO = 0.25
    BULK_FLOOR_RATIO = 0.80
    BULK_WORST_DISCOUNT = 0.70

    def choose(
        self,
        profile: TradeProfile,
        opportunities,
        *,
        max_age_hours=8.0,
        max_bulk_discount=0.08,
        max_profit_sacrifice=0.08,
    ):
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
            maximum_demand_ratio = self._demand_ratio_for_discount(max_bulk_discount)
            safe_demand_units=max(1,math.floor(max(0,item.demand)*maximum_demand_ratio))
            units=min(profile.cargo_free,profile.available_capital//item.buy_price,
                      max(0,item.supply),max(0,item.demand),safe_demand_units)
            if units<=0 or item.jumps<0: continue
            bulk_discount=self._bulk_discount(units,item.demand)
            estimated_sell_price=math.floor(item.sell_price*(1.0-bulk_discount))
            if estimated_sell_price<=item.buy_price: continue
            profit=(estimated_sell_price-item.buy_price)*units
            minutes=max(1.0, 4.0+item.jumps*1.25+self._supercruise_minutes(item.station_distance_ls))
            utilization=units/profile.cargo_free if profile.cargo_free else 0.0
            plans.append(QuickTradePlan(item,units,item.buy_price*units,profit,minutes,
                                        profit/minutes,age,units,bulk_discount,
                                        estimated_sell_price,utilization))
        if not plans:
            return None
        best_profit_rate=max(plan.profit_per_minute for plan in plans)
        acceptable=[
            plan for plan in plans
            if plan.profit_per_minute>=best_profit_rate*(1.0-max_profit_sacrifice)
        ]
        return max(acceptable,key=lambda plan:(plan.cargo_utilization,plan.profit_per_minute))

    @classmethod
    def _bulk_discount(cls, units: int, demand: int) -> float:
        if demand<=0: return 1.0
        ratio=units/demand
        if ratio<=cls.BULK_FULL_PRICE_RATIO: return 0.0
        progress=min(1.0,(ratio-cls.BULK_FULL_PRICE_RATIO)/(
            cls.BULK_FLOOR_RATIO-cls.BULK_FULL_PRICE_RATIO
        ))
        return progress*cls.BULK_WORST_DISCOUNT

    @classmethod
    def _demand_ratio_for_discount(cls, discount: float) -> float:
        accepted=max(0.0,min(cls.BULK_WORST_DISCOUNT,float(discount)))
        return cls.BULK_FULL_PRICE_RATIO+(
            accepted/cls.BULK_WORST_DISCOUNT
        )*(cls.BULK_FLOOR_RATIO-cls.BULK_FULL_PRICE_RATIO)

    @staticmethod
    def _supercruise_minutes(distance_ls):
        return min(20.0, 0.8+math.sqrt(max(0.0,distance_ls))/18.0)
    @staticmethod
    def _age_hours(value):
        try:
            stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
            return max(0.0,(datetime.now(timezone.utc)-stamp).total_seconds()/3600)
        except (ValueError,TypeError): return math.inf


class ThreeStationOptimizer:
    """Construye un circuito comercial factible A → B → C → A."""

    def __init__(self, quick_optimizer: QuickRouteOptimizer | None = None) -> None:
        self.quick = quick_optimizer or QuickRouteOptimizer()

    def choose(
        self,
        profile: TradeProfile,
        opportunities,
        *,
        max_age_hours: float = 8.0,
        max_bulk_discount: float = 0.08,
    ) -> ThreeStationTradePlan | None:
        edges = list(opportunities)
        candidates: list[ThreeStationTradePlan] = []
        for first in edges:
            first_buy = self._station(first.buy_system, first.buy_station)
            first_sell = self._station(first.sell_system, first.sell_station)
            for second in edges:
                second_buy = self._station(second.buy_system, second.buy_station)
                second_sell = self._station(second.sell_system, second.sell_station)
                if second_buy != first_sell or second_sell in {first_buy, first_sell}:
                    continue
                for third in edges:
                    if self._station(third.buy_system, third.buy_station) != second_sell:
                        continue
                    if self._station(third.sell_system, third.sell_station) != first_buy:
                        continue
                    legs = tuple(
                        self.quick.choose(
                            profile,
                            [edge],
                            max_age_hours=max_age_hours,
                            max_bulk_discount=max_bulk_discount,
                            max_profit_sacrifice=0.0,
                        )
                        for edge in (first, second, third)
                    )
                    if any(leg is None for leg in legs):
                        continue
                    typed_legs = (legs[0], legs[1], legs[2])
                    minutes = sum(leg.estimated_minutes for leg in typed_legs)
                    profit = sum(leg.estimated_profit for leg in typed_legs)
                    candidates.append(
                        ThreeStationTradePlan(
                            typed_legs,
                            profit,
                            minutes,
                            profit / max(1.0, minutes),
                            sum(leg.opportunity.jumps for leg in typed_legs),
                        )
                    )
        return max(
            candidates,
            key=lambda plan: (plan.profit_per_minute, plan.estimated_profit),
            default=None,
        )

    @staticmethod
    def _station(system: str, station: str) -> tuple[str, str]:
        return system.casefold(), station.casefold()


class TradeExpeditionOptimizer:
    """Encadena operaciones rentables sin superar el presupuesto de saltos."""

    def __init__(self, quick_optimizer: QuickRouteOptimizer | None = None) -> None:
        self.quick = quick_optimizer or QuickRouteOptimizer()

    def choose(
        self,
        profile: TradeProfile,
        opportunities,
        *,
        max_jumps: int = 30,
        max_legs: int = 8,
        beam_width: int = 100,
        max_age_hours: float = 8.0,
        max_bulk_discount: float = 0.08,
    ) -> TradeExpeditionPlan | None:
        if max_jumps <= 0 or max_legs <= 0:
            return None
        feasible: list[tuple[int, QuickTradePlan]] = []
        for index, opportunity in enumerate(opportunities):
            leg = self.quick.choose(
                profile,
                [opportunity],
                max_age_hours=max_age_hours,
                max_bulk_discount=max_bulk_discount,
                max_profit_sacrifice=0.0,
            )
            if leg is not None and 0 <= opportunity.jumps <= max_jumps:
                feasible.append((index, leg))
        if not feasible:
            return None

        states = [
            ((index,), (leg,))
            for index, leg in feasible
        ]
        candidates = list(states)
        for _ in range(1, max_legs):
            expanded = []
            for used, legs in states:
                last = legs[-1].opportunity
                current_station = self._station(
                    last.sell_system, last.sell_station
                )
                jumps_used = sum(leg.opportunity.jumps for leg in legs)
                for index, leg in feasible:
                    if index in used:
                        continue
                    next_opportunity = leg.opportunity
                    if self._station(
                        next_opportunity.buy_system,
                        next_opportunity.buy_station,
                    ) != current_station:
                        continue
                    if jumps_used + next_opportunity.jumps > max_jumps:
                        continue
                    expanded.append((used + (index,), legs + (leg,)))
            if not expanded:
                break
            expanded.sort(
                key=lambda state: self._state_score(state[1]), reverse=True
            )
            states = expanded[:max(1, beam_width)]
            candidates.extend(states)

        best = max(
            candidates,
            key=lambda state: self._state_score(state[1]),
            default=None,
        )
        if best is None:
            return None
        legs = best[1]
        profit = sum(leg.estimated_profit for leg in legs)
        minutes = sum(leg.estimated_minutes for leg in legs)
        jumps = sum(leg.opportunity.jumps for leg in legs)
        return TradeExpeditionPlan(
            legs,
            profit,
            minutes,
            profit / max(1.0, minutes),
            jumps,
        )

    @staticmethod
    def _state_score(legs: tuple[QuickTradePlan, ...]) -> tuple[int, float]:
        profit = sum(leg.estimated_profit for leg in legs)
        minutes = sum(leg.estimated_minutes for leg in legs)
        return profit, profit / max(1.0, minutes)

    @staticmethod
    def _station(system: str, station: str) -> tuple[str, str]:
        return system.casefold(), station.casefold()
