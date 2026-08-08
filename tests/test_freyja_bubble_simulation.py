"""Escenarios sintéticos de comercio dentro de la Burbuja."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.database import DatabaseManager
from freyja.market_source import MarketCache
from freyja.planner import (
    MarketOpportunity,
    QuickRouteOptimizer,
    ThreeStationOptimizer,
    TradeExpeditionOptimizer,
    TradeProfile,
    PowerplayTradeOptimizer,
)


class FreyjaBubbleSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(Path(self.temp.name))
        self.database.connect()
        self.database.create_tables()
        self.cache = MarketCache(self.database)
        self.now = datetime.now(timezone.utc).isoformat()

    def tearDown(self) -> None:
        self.database.disconnect()
        self.temp.cleanup()

    def opportunity(
        self,
        *,
        commodity: str = "oro",
        buy_price: int = 10_000,
        sell_price: int = 20_000,
        supply: int = 1_000,
        demand: int = 1_000,
        jumps: int = 2,
        distance_ls: float = 500,
        updated_at: str | None = None,
        buy_has_large_pad: bool = True,
        sell_has_large_pad: bool = True,
        buy_planetary: bool = False,
        sell_planetary: bool = False,
    ) -> MarketOpportunity:
        return MarketOpportunity(
            commodity,
            "Sistema Compra",
            "Puerto Compra",
            "Sistema Venta",
            "Puerto Venta",
            buy_price,
            sell_price,
            supply,
            demand,
            jumps,
            distance_ls,
            updated_at or self.now,
            buy_has_large_pad,
            sell_has_large_pad,
            buy_planetary,
            sell_planetary,
        )

    def test_small_ship_is_limited_by_available_capital(self) -> None:
        profile = TradeProfile("Sol", 100_000, 50_000, 32, 0, 25, (0, 0, 0))

        plan = QuickRouteOptimizer().choose(profile, [self.opportunity()])

        self.assertEqual(plan.units, 5)
        self.assertEqual(plan.investment, 50_000)
        self.assertEqual(plan.estimated_profit, 50_000)
        self.assertEqual(plan.recommended_sale_tons, 5)

    def test_large_freighter_never_exceeds_observed_demand(self) -> None:
        profile = TradeProfile("Sol", 100_000_000, 5_000_000, 720, 20, 30, (0, 0, 0))

        plan = QuickRouteOptimizer().choose(
            profile,
            [self.opportunity(supply=900, demand=180)],
        )

        self.assertEqual(profile.cargo_free, 700)
        self.assertEqual(plan.units, 56)
        self.assertEqual(plan.recommended_sale_tons, 56)
        self.assertLessEqual(plan.estimated_bulk_discount, 0.08)

    def test_sale_quantity_stays_inside_accepted_bulk_discount(self) -> None:
        profile = TradeProfile(
            "Sol", 100_000_000, 5_000_000, 700, 0, 30, (0, 0, 0)
        )

        plan = QuickRouteOptimizer().choose(
            profile,
            [self.opportunity(supply=1_000, demand=1_003)],
        )

        self.assertEqual(plan.units, 313)
        self.assertEqual(plan.recommended_sale_tons, 313)
        self.assertLessEqual(plan.estimated_bulk_discount, 0.08)
        self.assertIn("vendé 313 toneladas", plan.sale_instruction())
        self.assertIn("Puerto Venta", plan.sale_instruction())
        self.assertIn("dentro del límite aceptado", plan.sale_instruction())

    def test_prefers_fuller_cargo_within_accepted_profit_sacrifice(self) -> None:
        profile = TradeProfile(
            "Sol", 100_000_000, 5_000_000, 100, 0, 30, (0, 0, 0)
        )
        fastest = self.opportunity(
            commodity="oro", supply=50, demand=10_000,
            buy_price=10_000, sell_price=30_000, jumps=1, distance_ls=100,
        )
        fuller = self.opportunity(
            commodity="plata", supply=100, demand=10_000,
            buy_price=10_000, sell_price=19_500, jumps=1, distance_ls=100,
        )

        plan = QuickRouteOptimizer().choose(profile, [fastest, fuller])

        self.assertEqual(plan.opportunity.commodity, "plata")
        self.assertEqual(plan.units, 100)
        self.assertEqual(plan.cargo_utilization, 1.0)

    def test_does_not_fill_cargo_when_profit_loss_exceeds_tolerance(self) -> None:
        profile = TradeProfile(
            "Sol", 100_000_000, 5_000_000, 100, 0, 30, (0, 0, 0)
        )
        best = self.opportunity(
            commodity="oro", supply=50, demand=10_000,
            buy_price=10_000, sell_price=30_000, jumps=1, distance_ls=100,
        )
        weak_full = self.opportunity(
            commodity="plata", supply=100, demand=10_000,
            buy_price=10_000, sell_price=18_000, jumps=1, distance_ls=100,
        )

        plan = QuickRouteOptimizer().choose(profile, [best, weak_full])

        self.assertEqual(plan.opportunity.commodity, "oro")

    def test_stale_prices_are_rejected(self) -> None:
        stale = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        profile = TradeProfile("Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0))

        plan = QuickRouteOptimizer().choose(
            profile,
            [self.opportunity(updated_at=stale)],
            max_age_hours=8,
        )

        self.assertIsNone(plan)

    def test_near_route_beats_slow_high_margin_route_per_minute(self) -> None:
        profile = TradeProfile("Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0))
        nearby = self.opportunity(
            commodity="plata", sell_price=18_000, jumps=1, distance_ls=300
        )
        slow = self.opportunity(
            commodity="paladio", sell_price=30_000, jumps=12, distance_ls=250_000
        )

        plan = QuickRouteOptimizer().choose(profile, [slow, nearby])

        self.assertEqual(plan.opportunity.commodity, "plata")

    def test_full_cargo_hold_produces_no_trade_plan(self) -> None:
        profile = TradeProfile("Sol", 10_000_000, 500_000, 100, 100, 30, (0, 0, 0))

        self.assertIsNone(
            QuickRouteOptimizer().choose(profile, [self.opportunity()])
        )

    def test_powerplay_trade_combines_profit_and_merit_eligibility(self) -> None:
        profile = TradeProfile(
            "Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0),
            powerplay_power="Aisling Duval",
        )
        eligible = self.opportunity(buy_price=10_000, sell_price=16_000)
        eligible = MarketOpportunity(
            **{
                field: getattr(eligible, field)
                for field in eligible.__dataclass_fields__
                if field not in {"sell_power", "sell_power_state"}
            },
            sell_power="Aisling Duval",
            sell_power_state="Fortified",
        )

        plan = PowerplayTradeOptimizer().choose(profile, [eligible])

        self.assertIsNotNone(plan)
        self.assertTrue(plan.merit_eligible)
        self.assertIsNone(plan.merit_estimate)
        self.assertGreater(plan.trade.estimated_profit, 0)
        self.assertIn("Compre", plan.summary())
        self.assertIn("sistema Sistema Compra", plan.summary())
        self.assertIn("sistema Sistema Venta", plan.summary())
        self.assertIn("confirmar\u00e1 con el Journal", plan.summary())

    def test_powerplay_trade_rejects_wrong_power_or_low_margin(self) -> None:
        profile = TradeProfile(
            "Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0),
            powerplay_power="Jerome Archer",
        )
        wrong_power = MarketOpportunity(
            "oro", "A", "A1", "B", "B1", 10_000, 20_000,
            1_000, 1_000, 1, 100, self.now,
            sell_power="Aisling Duval", sell_power_state="Stronghold",
        )
        low_margin = MarketOpportunity(
            "plata", "A", "A1", "C", "C1", 10_000, 13_000,
            1_000, 1_000, 1, 100, self.now,
            sell_power="Jerome Archer", sell_power_state="Fortified",
        )

        self.assertIsNone(
            PowerplayTradeOptimizer().choose(profile, [wrong_power, low_margin])
        )

    def test_powerplay_trade_rejects_fleet_carriers(self) -> None:
        profile = TradeProfile(
            "Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0),
            powerplay_power="Li Yong-Rui",
        )
        carrier = MarketOpportunity(
            "tritium", "A", "Compra", "B", "T3L-L4K", 10_000, 20_000,
            1_000, 10_000, 1, 100, self.now,
            sell_power="Li Yong-Rui", sell_power_state="Stronghold",
            sell_station_type="Fleet Carrier",
        )
        self.assertIsNone(PowerplayTradeOptimizer().choose(profile, [carrier]))

    def test_market_cache_estimates_bubble_jumps_from_ship_range(self) -> None:
        self.cache.ingest_spansh_station({
            "market_id": 101,
            "system_name": "Burbuja A",
            "name": "Estación Alfa",
            "system_x": 0,
            "system_y": 0,
            "system_z": 0,
            "distance_to_arrival": 250,
            "market_updated_at": self.now,
            "market": [{
                "commodity": "silver", "buy_price": 5_000,
                "sell_price": 4_000, "supply": 500, "demand": 0,
            }],
        })
        self.cache.ingest_spansh_station({
            "market_id": 202,
            "system_name": "Burbuja B",
            "name": "Estación Beta",
            "system_x": 45,
            "system_y": 0,
            "system_z": 0,
            "distance_to_arrival": 400,
            "power": {"name": "Aisling Duval"},
            "power_state": "Fortified",
            "market_updated_at": self.now,
            "market": [{
                "commodity": "silver", "buy_price": 0,
                "sell_price": 12_000, "supply": 0, "demand": 200,
            }],
        })
        profile = TradeProfile(
            "Burbuja A", 5_000_000, 250_000, 64, 0, 20, (0, 0, 0)
        )

        opportunities = self.cache.opportunities(profile)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].jumps, 3)
        self.assertEqual(opportunities[0].station_distance_ls, 650)
        self.assertEqual(opportunities[0].sell_power, "Aisling Duval")
        self.assertEqual(opportunities[0].sell_power_state, "Fortified")

    def test_missing_position_or_jump_range_fails_conservatively(self) -> None:
        no_position = TradeProfile("Sol", 1_000_000, 50_000, 32, 0, 20, None)
        no_range = TradeProfile("Sol", 1_000_000, 50_000, 32, 0, 0, (0, 0, 0))

        self.assertEqual(self.cache.opportunities(no_position), [])
        self.assertEqual(self.cache.opportunities(no_range), [])

    def test_three_station_chain_closes_cycle_with_three_products(self) -> None:
        profile = TradeProfile(
            "Sistema A", 20_000_000, 1_000_000, 100, 0, 30, (0, 0, 0)
        )
        a_to_b = MarketOpportunity(
            "oro", "Sistema A", "Estación A", "Sistema B", "Estación B",
            10_000, 18_000, 1_000, 1_000, 2, 400, self.now,
        )
        b_to_c = MarketOpportunity(
            "plata", "Sistema B", "Estación B", "Sistema C", "Estación C",
            8_000, 14_000, 1_000, 1_000, 3, 500, self.now,
        )
        c_to_a = MarketOpportunity(
            "medicinas", "Sistema C", "Estación C", "Sistema A", "Estación A",
            4_000, 9_000, 1_000, 1_000, 2, 300, self.now,
        )

        plan = ThreeStationOptimizer().choose(
            profile, [a_to_b, b_to_c, c_to_a]
        )

        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.legs), 3)
        self.assertEqual(
            tuple(leg.opportunity.commodity for leg in plan.legs),
            ("oro", "plata", "medicinas"),
        )
        self.assertEqual(plan.total_jumps, 7)
        self.assertGreater(plan.estimated_profit, 0)
        self.assertIn("Estación A → Estación B → Estación C → Estación A", plan.summary())

    def test_three_station_chain_rejects_open_or_incompatible_cycle(self) -> None:
        profile = TradeProfile(
            "Sistema A", 20_000_000, 1_000_000, 100, 0, 30, (0, 0, 0),
            requires_large_pad=True,
        )
        a_to_b = self.opportunity()
        b_to_c = MarketOpportunity(
            "plata", "Sistema Venta", "Puerto Venta", "Sistema C", "Estación C",
            8_000, 14_000, 1_000, 1_000, 2, 500, self.now,
            sell_has_large_pad=False,
        )

        self.assertIsNone(
            ThreeStationOptimizer().choose(profile, [a_to_b, b_to_c])
        )

    def test_trade_expedition_maximizes_profit_without_exceeding_30_jumps(self) -> None:
        profile = TradeProfile(
            "Sistema A", 50_000_000, 2_500_000, 200, 0, 30, (0, 0, 0)
        )
        legs = [
            MarketOpportunity(
                f"producto {index}",
                f"Sistema {letter}", f"Estación {letter}",
                f"Sistema {chr(ord(letter) + 1)}", f"Estación {chr(ord(letter) + 1)}",
                5_000, 10_000 + index * 1_000,
                2_000, 2_000, 8, 300, self.now,
            )
            for index, letter in enumerate(("A", "B", "C", "D"), start=1)
        ]

        plan = TradeExpeditionOptimizer().choose(profile, legs, max_jumps=30)

        self.assertIsNotNone(plan)
        self.assertEqual(plan.total_jumps, 24)
        self.assertEqual(len(plan.legs), 3)
        self.assertLessEqual(plan.total_jumps, 30)
        self.assertGreater(plan.estimated_profit, 0)
        self.assertIn("24 saltos", plan.summary())

    def test_trade_expedition_rejects_invalid_budget_and_disconnected_edges(self) -> None:
        profile = TradeProfile(
            "Sistema A", 5_000_000, 250_000, 64, 0, 25, (0, 0, 0)
        )
        disconnected = [
            self.opportunity(commodity="oro", jumps=16),
            MarketOpportunity(
                "plata", "Otro A", "Otro Puerto", "Otro B", "Destino",
                5_000, 12_000, 500, 500, 16, 500, self.now,
            ),
        ]

        plan = TradeExpeditionOptimizer().choose(
            profile, disconnected, max_jumps=30
        )

        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.legs), 1)
        self.assertEqual(plan.total_jumps, 16)
        self.assertIsNone(
            TradeExpeditionOptimizer().choose(profile, disconnected, max_jumps=0)
        )

    def test_large_ship_rejects_route_without_large_pads(self) -> None:
        profile = TradeProfile(
            "Sol", 100_000_000, 5_000_000, 700, 0, 30, (0, 0, 0),
            requires_large_pad=True,
        )
        incompatible = self.opportunity(sell_has_large_pad=False)

        self.assertIsNone(QuickRouteOptimizer().choose(profile, [incompatible]))

    def test_orbital_profile_rejects_planetary_station(self) -> None:
        profile = TradeProfile(
            "Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0),
            allow_planetary=False,
        )

        self.assertIsNone(
            QuickRouteOptimizer().choose(
                profile, [self.opportunity(sell_planetary=True)]
            )
        )

    def test_excluded_or_permit_locked_system_is_never_used(self) -> None:
        profile = TradeProfile(
            "Sol", 10_000_000, 500_000, 100, 0, 30, (0, 0, 0),
            excluded_systems=frozenset({"Sistema Venta"}),
        )

        self.assertIsNone(
            QuickRouteOptimizer().choose(profile, [self.opportunity()])
        )


if __name__ == "__main__":
    unittest.main()
